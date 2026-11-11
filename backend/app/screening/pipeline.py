"""CV pipeline: parse -> (profile || injection scan) -> anonymize -> evaluate -> verify quotes -> triage."""
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from sqlalchemy import delete

from ..audit import log_event
from ..cv.anonymize import anonymize
from ..cv.parse import UnsupportedFile, parse_cv
from ..db import SessionLocal
from ..llm import LLMError, llm
from ..models import Candidate, Criterion, Evaluation, now
from ..prompts import (
    EVAL_SYSTEM,
    EVAL_USER,
    INJECTION_SYSTEM,
    INJECTION_USER,
    PROFILE_SYSTEM,
    PROFILE_USER,
    PROMPT_VERSION,
    TRANSCRIBE_SYSTEM,
)
from ..schemas import CVEvaluation, InjectionScan, Profile, Transcription
from .triage import PREQUAL, triage
from .verify import verify_quote

log = logging.getLogger("pipeline")
_SEM = threading.Semaphore(4)  # at most 4 candidates in flight (API rate limits)

# Cheap deterministic net on top of the LLM scan. It only matches text that gives the screening system an ORDER
# or is ADDRESSED to it. Achievements ("note maximale au CACES", "highest score in the audit") and ordinary job
# vocabulary ("système automatisé de stockage", "AI deployment lead") must never flag a CV on their own.
_TARGET = (r"(?:syst[èe]me\s+(?:automatis[ée]e?|de\s+(?:tri|recrutement|s[ée]lection))|\bia\b|\bai\b|intelligence\s+artificielle"
           r"|automated\s+(?:screening|system|recruit\w*)|screening\s+(?:system|tool|bot)|\bats\b|\bllm\b|algorithme|robot)")
_INJ_RE = re.compile(
    r"(ignore[zr]?\s+(?:toutes?\s+)?(?:les\s+)?(?:instructions|consignes)"
    r"|(?:ignore|disregard|forget)\s+(?:all\s+)?(?:the\s+|your\s+|any\s+)?(?:previous|prior|above)\s+(?:instructions|prompts?|rules)"
    r"|(?:attribue[zr]?|donne[zr]?|accorde[zr]?)-lui|classe[zr]?-le\s+en\s+(?:priorit[ée]|t[êe]te)"
    r"|(?:give|assign|award)\s+(?:him|her|them|this\s+(?:candidate|cv|resume)|the\s+candidate)\b"
    r"|rank\s+(?:him|her|them|this\s+(?:candidate|cv|resume))\s+(?:first|highest|top)"
    r"|(?:à\s+l['’]attention\s+(?:du|de\s+l['’]|des)|(?:note|message|instructions?)\s+(?:au|à\s+l['’]|pour\s+(?:le|l['’])|to\s+the|for\s+the))\s*"
    + _TARGET +
    r"|you\s+are\s+now\s+(?:a|an|the)\b"
    r"|system\s+(?:override|prompt)|(?:disregard|ignore|ignore[zr])\s+(?:the\s+|les\s+)?(?:job\s+)?(?:criteria|crit[èe]res)"
    r"|(?:output|return|set)\s+(?:the\s+)?(?:verdict|score|rating)\b"
    r"|(?:this|the)\s+candidate\s+is\s+(?:a\s+)?(?:perfect|ideal)|ce\s+candidat\s+(?:correspond\s+parfaitement|est\s+(?:le\s+)?(?:candidat\s+)?id[ée]al))",
    re.I,
)


def _verified(text: str, items: list[str]) -> list[str]:
    return [e for e in items if e and verify_quote(e, text, fuzzy=0.85)[0]]


def _u(c, purpose: str) -> dict:
    return {"job_id": c.job_id, "candidate_id": c.id, "purpose": purpose}


def _scan_injection(visible: str, hidden: list[str], usage: dict | None = None) -> tuple[bool, list[str]]:
    hid = "\n".join(hidden)
    evidence: list[str] = []
    for m in _INJ_RE.finditer(visible + "\n" + hid):
        evidence.append(m.group(0))
    flagged = bool(evidence)
    try:
        scan = llm.structured(
            "fast", INJECTION_SYSTEM, INJECTION_USER.format(visible=visible[:12000], hidden=hid[:3000] or "(aucun)"),
            InjectionScan, max_tokens=1000, usage=usage,
        )
        if scan.injected:
            flagged = True
            evidence += _verified(visible + "\n" + hid, scan.evidence)
    except LLMError as e:
        log.warning("injection scan failed: %s", e)
    # Hidden text is ALWAYS kept away from the evaluator (see cv/parse.py), but on its own it is not an attack
    # (design tools, white keywords, layout artefacts). It raises the flag only when it carries an instruction,
    # i.e. when the regex or the LLM scan found one. Then the whole hidden passage is shown first, as evidence.
    if flagged and hid.strip():
        evidence = [hid.strip()[:400], *evidence]
    return flagged, list(dict.fromkeys(evidence))[:5]


def _fmt_criteria(crits: list[Criterion]) -> str:
    return "\n".join(
        f"- id={c.id} [{'INDISPENSABLE' if c.kind == 'must' else 'souhaité'}] {c.label}: {c.description}" for c in crits
    )


def _prequal_label(t: str) -> str:
    return PREQUAL.get(t, "")


def process_candidate(candidate_id: int):
    with _SEM:
        db = SessionLocal()
        try:
            _process(db, candidate_id)
        except Exception as e:  # never leave a candidate in limbo
            log.exception("pipeline failed for %s", candidate_id)
            c = db.get(Candidate, candidate_id)
            if c:
                c.status, c.error = "failed", str(e)[:500]
                db.commit()
        finally:
            db.close()


def _process(db, candidate_id: int):
    c = db.get(Candidate, candidate_id)
    if not c:
        return
    today = date.today().isoformat()
    c.status, c.error = "parsing", ""
    db.commit()

    # 1. parse
    try:
        parsed = parse_cv(c.file_bytes or b"", c.filename, c.mime)
    except UnsupportedFile as e:
        c.status, c.error = "failed", str(e)
        db.commit()
        return
    text = parsed.text
    if parsed.needs_vision and c.file_bytes:
        mime = parsed.vision_mime or "application/pdf"
        t = llm.structured("fast", TRANSCRIBE_SYSTEM, "Transcris ce CV.", Transcription,
                           files=[(mime, c.file_bytes)], max_tokens=8000,
                           usage=_u(c, "transcribe"))
        text = t.text.strip()
    if len(text) < 80:
        c.status, c.error = "failed", "Document illisible ou vide (aucun texte exploitable)."
        db.commit()
        return
    c.text_raw, c.hidden_text = text, parsed.hidden
    c.status = "screening"
    db.commit()

    # 2. profile + injection scan in parallel
    with ThreadPoolExecutor(2) as ex:
        f_prof = ex.submit(
            llm.structured, "fast", PROFILE_SYSTEM, PROFILE_USER.format(today=today, text=text[:15000]), Profile,
            usage=_u(c, "profile"),
        )
        f_inj = ex.submit(_scan_injection, text, parsed.hidden, _u(c, "injection"))
        profile: Profile = f_prof.result()
        inj_flag, inj_evidence = f_inj.result()

    # code-verified contact info: must literally exist in the CV
    if profile.email and profile.email.lower() not in text.lower():
        profile.email = ""
    digits = re.sub(r"\D", "", text)
    if profile.phone and re.sub(r"\D", "", profile.phone) not in digits:
        profile.phone = ""
    c.profile = profile.model_dump()
    c.lang = (profile.cv_language or "fr")[:5]
    c.injection_flag, c.injection_evidence = inj_flag, inj_evidence

    if not profile.is_cv:
        c.status, c.error = "failed", "Le document ne semble pas être un CV."
        db.commit()
        return

    # 3. anonymize (visible text only: hidden text never reaches the evaluator)
    c.text_anon = anonymize(text, c.profile)
    db.commit()

    # 4. evaluate CV-source criteria
    crits = [k for k in c.job.criteria if k.source == "cv"]
    ev = llm.structured(
        "smart", EVAL_SYSTEM,
        EVAL_USER.format(today=today, criteria=_fmt_criteria(crits), text=c.text_anon[:15000]),
        CVEvaluation, max_tokens=4000, usage=_u(c, "evaluate"),
    )
    by_id = {e.criterion_id: e for e in ev.evaluations}
    db.execute(delete(Evaluation).where(Evaluation.candidate_id == c.id))
    items, doubt = [], False
    for k in crits:
        e = by_id.get(k.id)
        verdict, quote, why, ok = (e.verdict, e.quote, e.rationale, False) if e else ("not_evidenced", "", "Non évalué.", False)
        if verdict != "not_evidenced":
            ok, _ = verify_quote(quote, c.text_anon)
            if not ok:  # no verified quote, no verdict
                doubt = doubt or (k.kind == "must" and verdict == "not_met")
                why = f"[citation non vérifiée, verdict initial: {verdict}] {why}"
                verdict, quote = "not_evidenced", ""
        db.add(Evaluation(candidate_id=c.id, criterion_id=k.id, verdict=verdict, quote=quote,
                          quote_verified=ok, rationale=why))
        items.append((k.kind, verdict))

    # 5. triage (pure code)
    score, tri = triage(items, injection=c.injection_flag, doubt=doubt)
    c.cv_score, c.triage, c.prequal = score, tri, _prequal_label(tri)
    c.summary = ev.summary
    c.status = "screened"
    c.screened_at = now()
    db.commit()
    log_event(db, "IA", "cv_screened", "candidate", c.id, triage=tri, score=round(score, 2),
              injection=c.injection_flag, prompt_version=PROMPT_VERSION)

    if tri == "yes":  # pre-qualified: interview ready (plan + unique link) without waiting for the recruiter
        try:
            from ..interview.service import ensure_interview
            ensure_interview(db, c)
            from ..config import settings as _s
            if _s.auto_send_invites:
                from ..comms import send_pending_invite
                db.refresh(c)
                send_pending_invite(db, c)
        except Exception as e:  # noqa: BLE001  the recruiter can still click "Inviter"
            log.warning("auto interview prep failed for %s: %s", c.id, e)
