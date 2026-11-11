"""Replies: a personalised e-mail is drafted for every candidate and sent only once the recruiter approves it."""
import logging

from sqlalchemy.orm import Session

from .audit import log_event
from .config import settings
from .db import SessionLocal
from .emailtpl import build_html
from .llm import llm
from .mailer import MailError, send_email
from .models import Candidate, Message, now
from .prompts import DRAFT_SYSTEM, DRAFT_USER
from .schemas import Draft
from .util import format_date

log = logging.getLogger("comms")


def message_language(c: Candidate) -> str:
    if c.interview and c.interview.language:
        return c.interview.language
    return "en" if (c.lang or "fr").startswith("en") else "fr"


def draft_message(db: Session, c: Candidate, kind: str) -> Message:
    by_id = {k.id: k for k in c.job.criteria}
    strengths = [by_id[e.criterion_id].label for e in c.evaluations if e.verdict == "met" and e.criterion_id in by_id][:3]
    gaps = [f"{by_id[e.criterion_id].label} ({e.rationale})" for e in c.evaluations
            if e.verdict in ("not_met", "partial") and e.criterion_id in by_id and by_id[e.criterion_id].kind == "must"][:2]
    name = ((c.profile or {}).get("name") or "").split()
    lang = message_language(c)
    link = f"{settings.public_url}/i/{c.token}" if c.token else ""
    expires = format_date(c.interview.expires_at, lang) if c.interview else ""
    d = llm.structured(
        "fast", DRAFT_SYSTEM,
        DRAFT_USER.format(kind=kind, language="English" if lang == "en" else "français", first_name=name[0].title() if name else "",
                          job=c.job.title, link=link or "-", expires=expires or "-", strengths="; ".join(strengths) or "-", gaps="; ".join(gaps) or "-"),
        Draft, max_tokens=900, usage={"job_id": c.job_id, "candidate_id": c.id, "purpose": f"draft_{kind}"},
    )
    body = d.body.strip()
    if kind == "invite":  # guarantee the access link and the deadline are in the e-mail, whatever the model wrote
        if link and link not in body:
            body += f"\n\n{'Lien d' + chr(39) + 'accès' if lang == 'fr' else 'Access link'} : {link}"
        if expires and expires not in body:
            body += f"\n{'Ce lien est valable jusqu' + chr(39) + 'au ' if lang == 'fr' else 'This link is valid until '}{expires}."
    m = Message(candidate_id=c.id, kind=kind, language=lang, subject=d.subject, body=body, status="draft")
    db.add(m)
    db.commit()
    log_event(db, "IA", "message_drafted", "candidate", c.id, kind=kind)
    return m


def draft_in_background(candidate_id: int, kind: str):
    db = SessionLocal()
    try:
        c = db.get(Candidate, candidate_id)
        if c and not any(m.kind == kind and m.status != "sent" for m in c.messages):
            draft_message(db, c, kind)
    except Exception as e:  # noqa: BLE001
        log.warning("draft %s failed for %s: %s", kind, candidate_id, e)
    finally:
        db.close()


def ai_proposal(c: Candidate) -> str:
    """accept | reject | review — what the AI suggests. The recruiter decides.

    After the interview, the model's recommendation is only followed when the interview can be trusted:
    a manipulation attempt, or too few criteria assessed to compute a note, never yields "accept"."""
    iv = c.interview
    if iv and iv.status == "scored" and iv.synthesis.get("recommendation"):
        proposal = {"invite": "accept", "decline": "reject", "hold": "review"}[iv.synthesis["recommendation"]]
        if iv.synthesis.get("manipulation") and proposal == "accept":
            return "review"
        if (iv.scores or {}).get("note") is None:   # interview too short: nothing reliable to propose
            return "review"
        return proposal
    if c.triage == "no":
        return "reject"
    return "review"


def _html_for(m: Message) -> str:
    c, lang = m.candidate, m.language
    if m.kind == "invite" and c.token:
        link = f"{settings.public_url}/i/{c.token}"
        label = "Start the pre-interview" if lang == "en" else "Passer le pré-entretien"
        note = None
        if c.interview and c.interview.expires_at:
            d = format_date(c.interview.expires_at, lang)
            note = f"This link is valid until {d}." if lang == "en" else f"Ce lien est valable jusqu'au {d}."
        return build_html(m.body, cta_label=label, cta_url=link, note=note, lang=lang)
    return build_html(m.body, lang=lang)


def mark_sent(db: Session, m: Message, actor: str):
    """Deliver the (approved) message. Raises MailError if delivery fails: the message then stays a draft."""
    to = (m.candidate.profile or {}).get("email", "")
    transport = send_email(to, m.subject, m.body, html=_html_for(m))
    m.status, m.sent_at, m.transport = "sent", now(), transport
    db.commit()
    log_event(db, actor, "message_sent", "candidate", m.candidate_id, kind=m.kind, to=to, transport=transport)


def send_pending_invite(db: Session, c: Candidate, actor: str = "système") -> bool:
    """Used by AUTO_SEND_INVITES: send the invitation draft of a pre-qualified candidate. Never raises."""
    m = next((x for x in reversed(c.messages) if x.kind == "invite" and x.status == "draft"), None)
    if not m:
        return False
    try:
        log_event(db, actor, "message_approved", "candidate", c.id, kind="invite", automatic=True)
        mark_sent(db, m, actor)
        return True
    except MailError as e:
        log.warning("auto-send invite failed for %s: %s", c.id, e)
        return False
