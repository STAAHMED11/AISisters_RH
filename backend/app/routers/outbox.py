from flask import Blueprint
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..audit import log_event
from ..comms import ai_proposal, draft_in_background, mark_sent
from ..config import settings
from ..mailer import MailError, send_email
from ..mailer import status as mail_state
from ..models import Candidate, Decision, Message
from ..web import HTTPException, background, login_required, parse
from ..web import db as get_session
from .jobs import get_job_or_404

bp = Blueprint("outbox", __name__, url_prefix="/api")


class DecisionIn(BaseModel):
    decision: str  # accept | reject
    comment: str = ""


def record_decision(db: Session, c: Candidate, decision: str, comment: str, actor: str) -> Decision:
    proposed = ai_proposal(c)
    override = proposed in ("accept", "reject") and decision != proposed
    d = Decision(candidate_id=c.id, actor=actor, decision=decision, ai_proposed=proposed, comment=comment.strip())
    db.add(d)
    c.decision = "accepted" if decision == "accept" else "rejected"
    db.commit()
    log_event(db, actor, "decision_override" if override else "decision", "candidate", c.id,
              decision=decision, ai_proposed=proposed, comment=comment.strip())
    return d


@bp.post("/candidates/<int:cid>/decision")
@login_required
def decide(cid: int, user: str):
    db, body = get_session(), parse(DecisionIn)
    c = db.get(Candidate, cid)
    if not c or c.status != "screened":
        raise HTTPException(404, "Candidat introuvable ou non analysé")
    if body.decision not in ("accept", "reject"):
        raise HTTPException(400, "Décision invalide")
    proposed = ai_proposal(c)
    if proposed in ("accept", "reject") and body.decision != proposed and len(body.comment.strip()) < 5:
        raise HTTPException(400, "Vous allez à l'encontre de la proposition de l'IA : un commentaire est obligatoire.")
    record_decision(db, c, body.decision, body.comment, user)
    background(draft_in_background, c.id, "acceptance" if body.decision == "accept" else "rejection")
    return {"ok": True, "override": proposed in ("accept", "reject") and body.decision != proposed}


@bp.post("/jobs/<int:job_id>/reject-batch")
@login_required
def reject_batch(job_id: int, user: str):
    """Validate, in one click, the rejections the AI proposed (triage = no, no decision yet). Letters still need approval."""
    db = get_session()
    job = get_job_or_404(db, job_id)
    todo = [c for c in job.candidates if c.status == "screened" and c.triage == "no" and not c.decision]
    for c in todo:
        record_decision(db, c, "reject", "Refus validé en lot", user)
        background(draft_in_background, c.id, "rejection")
    return {"count": len(todo)}


def message_dict(m: Message) -> dict:
    p = m.candidate.profile or {}
    return {"transport": m.transport, "id": m.id, "candidate_id": m.candidate_id, "name": p.get("name") or m.candidate.filename, "email": p.get("email", ""),
            "kind": m.kind, "language": m.language, "subject": m.subject, "body": m.body, "status": m.status,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None, "created_at": m.created_at.isoformat()}


@bp.get("/jobs/<int:job_id>/outbox")
@login_required
def outbox(job_id: int, user: str):
    db = get_session()
    job = get_job_or_404(db, job_id)
    msgs = [m for c in job.candidates for m in c.messages]
    msgs.sort(key=lambda m: m.id, reverse=True)
    final_sent = {m.candidate_id for m in msgs if m.kind in ("acceptance", "rejection") and m.status == "sent"}
    decided = [c for c in job.candidates if c.decision]
    proposed_rej = [c for c in job.candidates if c.status == "screened" and c.triage == "no" and not c.decision]
    return {
        "messages": [message_dict(m) for m in msgs],
        "stats": {
            "candidates": len(job.candidates),
            "decided": len(decided),
            "awaiting_reply": len([c for c in decided if c.id not in final_sent]),
            "replied": len(final_sent),
            "rejections_to_validate": len(proposed_rej),
        },
    }


class MsgEdit(BaseModel):
    subject: str
    body: str


def _msg(db: Session, mid: int) -> Message:
    m = db.get(Message, mid)
    if not m:
        raise HTTPException(404, "Message introuvable")
    return m


@bp.put("/messages/<int:mid>")
@login_required
def edit_message(mid: int, user: str):
    db, body = get_session(), parse(MsgEdit)
    m = _msg(db, mid)
    if m.status == "sent":
        raise HTTPException(409, "Message déjà envoyé")
    m.subject, m.body = body.subject.strip(), body.body.strip()
    db.commit()
    log_event(db, user, "message_edited", "candidate", m.candidate_id, kind=m.kind)
    return message_dict(m)


@bp.post("/messages/<int:mid>/send")
@login_required
def send_message(mid: int, user: str):
    db = get_session()
    m = _msg(db, mid)
    if m.status != "sent":
        log_event(db, user, "message_approved", "candidate", m.candidate_id, kind=m.kind)
        try:
            mark_sent(db, m, user)
        except MailError as e:
            raise HTTPException(502, str(e)) from e
    return message_dict(m)


@bp.delete("/messages/<int:mid>")
@login_required
def delete_message(mid: int, user: str):
    db = get_session()
    m = _msg(db, mid)
    if m.status == "sent":
        raise HTTPException(409, "Message déjà envoyé")
    db.delete(m)
    db.commit()
    return {"ok": True}


@bp.post("/jobs/<int:job_id>/outbox/send-all")
@login_required
def send_all(job_id: int, user: str):
    db = get_session()
    job = get_job_or_404(db, job_id)
    n, failed = 0, []
    for c in job.candidates:
        for m in c.messages:
            if m.status == "draft":
                log_event(db, user, "message_approved", "candidate", c.id, kind=m.kind, batch=True)
                try:
                    mark_sent(db, m, user)
                    n += 1
                except MailError as e:
                    failed.append({"name": (c.profile or {}).get("name") or c.filename, "error": str(e)})
    return {"sent": n, "failed": failed}


@bp.get("/mail-status")
@login_required
def mail_status(user: str):
    return mail_state()


class MailTest(BaseModel):
    to: str


@bp.post("/mail-test")
@login_required
def mail_test(user: str):
    """Checks the SMTP settings end to end by sending a short test message to an address you choose."""
    body = parse(MailTest)
    from ..emailtpl import build_html
    text = "Ceci est un e-mail de test de l'application RH du futur.\n\nSi vous le lisez, l'envoi des invitations et des réponses aux candidats fonctionne."
    try:
        transport = send_email(body.to, "Test d'envoi · RH du futur", text, html=build_html(text, cta_label="Ouvrir l'application", cta_url=settings.public_url))
    except MailError as e:
        raise HTTPException(502, str(e)) from e
    return {"transport": transport}

