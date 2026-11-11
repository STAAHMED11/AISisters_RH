from flask import Blueprint, request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import log_event
from ..web import HTTPException, background, db as get_session, login_required, parse
from ..models import AuditLog, Candidate
from ..costs import candidate_costs
from ..comms import ai_proposal, draft_message, mark_sent
from ..mailer import MailError, configured
from ..util import aware, format_date
from datetime import timedelta
from ..models import now
from ..config import settings
from ..interview.service import create_interview, ensure_interview, ensure_invite_draft, has_plan, prepare_assets_bg, score_interview
from ..llm import LLMError
from ..screening.pipeline import process_candidate
from ..screening.verify import verify_quote
from .jobs import get_job_or_404

bp = Blueprint("candidates", __name__, url_prefix="/api")
MAX_BYTES = 10 * 1024 * 1024


def candidate_row(c: Candidate) -> dict:
    p = c.profile or {}
    return {
        "id": c.id,
        "filename": c.filename,
        "status": c.status,
        "error": c.error,
        "name": p.get("name") or c.filename,
        "email": p.get("email", ""),
        "phone": p.get("phone", ""),
        "city": p.get("city", ""),
        "title": p.get("current_title", ""),
        "years_experience": p.get("years_experience"),
        "education_level": p.get("education_level", ""),
        "languages": p.get("languages", []),
        "skills": p.get("skills", []),
        "headline": p.get("headline", ""),
        "lang": c.lang,
        "cv_score": c.cv_score,
        "interview_note": c.interview_note,
        "global_score": c.global_score,
        "triage": c.triage,
        "prequal": c.prequal,
        "injection_flag": c.injection_flag,
        "decision": c.decision,
        "has_interview": c.interview is not None,
        "invite_state": next((m.status for m in reversed(c.messages) if m.kind == "invite"), "none"),
        "interview_expired": bool(c.interview and c.interview.expires_at and c.interview.status in ("pending", "started") and now() > aware(c.interview.expires_at)),
        "interview_status": c.interview.status if c.interview else "",
        "summary": c.summary,
    }


def history(db: Session, cid: int) -> list[dict]:
    """The candidate's own timeline (what the AI, the recruiter and the candidate did), newest first."""
    rows = db.scalars(select(AuditLog).where(AuditLog.entity == "candidate", AuditLog.entity_id == cid)
                      .order_by(AuditLog.id.desc()).limit(200)).all()
    kind = {"IA": "ia", "candidat": "candidate", "système": "system"}
    return [{"id": r.id, "ts": r.ts.isoformat(), "actor": r.actor, "actor_type": kind.get(r.actor, "recruiter"),
             "action": r.action, "payload": r.payload} for r in rows]


def interview_dict(c: Candidate) -> dict | None:
    iv = c.interview
    if not iv:
        return None
    by_id = {k.id: k.label for k in c.job.criteria}
    scores = dict(iv.scores or {})
    for g in scores.get("grades", []):
        g["label"] = by_id.get(g["criterion_id"], "")
    inv = [m for m in c.messages if m.kind == "invite"]
    last = inv[-1] if inv else None
    expired = bool(iv.expires_at) and now() > aware(iv.expires_at) and iv.status in ("pending", "started")
    return {
        "invite": {"state": (last.status if last else "none"), "to": (c.profile or {}).get("email", ""),
                   "sent_at": last.sent_at.isoformat() if last and last.sent_at else None,
                   "transport": last.transport if last else "", "smtp": configured()},
        "expires_at": iv.expires_at.isoformat() if iv.expires_at else None,
        "expires_label": format_date(iv.expires_at, iv.language), "expired": expired,
        "plan_ready": has_plan(iv),
        "status": iv.status, "mode": iv.mode, "language": iv.language, "link": f"{settings.public_url}/i/{c.token}",
        "plan": iv.plan, "transcript": iv.transcript, "scores": scores, "synthesis": iv.synthesis,
        "consented": iv.consent_at is not None,
    }


@bp.post("/candidates/<int:cid>/invite")
@login_required
def invite(cid: int, user: str):
    """Instant: the link exists as soon as this returns. The AI question plan is prepared in the background."""
    db = get_session()
    c = db.get(Candidate, cid)
    if not c or c.status != "screened":
        raise HTTPException(400, "Le CV doit d'abord être analysé.")
    create_interview(db, c)
    background(prepare_assets_bg, c.id)
    log_event(db, user, "interview_invited", "candidate", c.id)
    return interview_dict(c)


class SendInvite(BaseModel):
    extend: bool = False


@bp.post("/candidates/<int:cid>/invite/send")
@login_required
def send_invite(cid: int, user: str):
    """Recruiter-approved: e-mail the interview link (with its deadline) to the candidate. extend=True renews the deadline."""
    db, body = get_session(), parse(SendInvite)
    c = db.get(Candidate, cid)
    if not c or c.status != "screened":
        raise HTTPException(400, "Le CV doit d'abord être analysé.")
    iv = create_interview(db, c)
    background(prepare_assets_bg, c.id)   # the plan is not needed to send the link: it is built meanwhile
    if iv.status in ("ended", "scored"):
        raise HTTPException(409, "L'entretien est déjà passé.")
    last = next((m for m in reversed(c.messages) if m.kind == "invite"), None)
    needs_new = body.extend or last is None
    if body.extend:
        iv.expires_at = now() + timedelta(days=settings.interview_valid_days)
        db.commit()
        log_event(db, user, "interview_extended", "candidate", c.id, expires=iv.expires_at.isoformat())
    if last is not None and last.status == "draft" and body.extend:
        db.delete(last)  # stale draft carries the old deadline
        db.commit()
        last = None
    if last is None or (last.status == "sent" and needs_new):
        try:
            last = ensure_invite_draft(db, c)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(502, f"Impossible de préparer l'e-mail : {e}")
    if last.status == "draft":
        log_event(db, user, "message_approved", "candidate", c.id, kind="invite")
        try:
            mark_sent(db, last, user)
        except MailError as e:
            raise HTTPException(502, str(e))
    db.refresh(c)
    return interview_dict(c)


@bp.post("/candidates/<int:cid>/rescore")
@login_required
def rescore(cid: int, user: str):
    db = get_session()
    c = db.get(Candidate, cid)
    if not c or not c.interview:
        raise HTTPException(404, "Pas d'entretien")
    if c.interview.mode == "voice" and c.interview.el_conversation_id:
        from ..interview.elevenlabs import fetch_and_score
        background(fetch_and_score, c.id, 20)
    else:
        background(score_interview, c.id)
    return {"ok": True}


@bp.post("/jobs/<int:job_id>/candidates")
@login_required
def upload_cvs(job_id: int, user: str):
    db = get_session()
    files = request.files.getlist("files")
    if not files:
        raise HTTPException(422, "files: au moins un fichier est requis")
    job = get_job_or_404(db, job_id)
    if not job.criteria:
        raise HTTPException(400, "Définissez d'abord les critères de l'offre.")
    created = []
    for f in files:
        data = f.read()
        if not data:
            continue
        if len(data) > MAX_BYTES:
            raise HTTPException(413, f"{f.filename}: fichier trop volumineux (10 Mo max).")
        c = Candidate(job_id=job.id, filename=f.filename or "cv", mime=f.mimetype or "", file_bytes=data)
        db.add(c)
        db.flush()
        created.append(c)
    db.commit()
    for c in created:
        log_event(db, user, "cv_uploaded", "candidate", c.id, filename=c.filename)
        background(process_candidate, c.id)
    return [{"id": c.id, "filename": c.filename} for c in created]


@bp.get("/jobs/<int:job_id>/candidates")
@login_required
def list_candidates(job_id: int, user: str):
    db = get_session()
    get_job_or_404(db, job_id)
    rows = db.scalars(select(Candidate).where(Candidate.job_id == job_id)).all()
    rows.sort(key=lambda c: (c.global_score if c.global_score is not None else (c.cv_score if c.cv_score is not None else -1)), reverse=True)
    return [candidate_row(c) for c in rows]


@bp.get("/candidates/<int:cid>")
@login_required
def get_candidate(cid: int, user: str):
    db = get_session()
    c = db.get(Candidate, cid)
    if not c:
        raise HTTPException(404, "Candidat introuvable")
    crit_by_id = {k.id: k for k in c.job.criteria}
    evals = []
    for e in c.evaluations:
        k = crit_by_id.get(e.criterion_id)
        span = verify_quote(e.quote, c.text_raw, fuzzy=0.85)[1] if e.quote else None
        evals.append({
            "criterion_id": e.criterion_id, "label": k.label if k else "", "description": k.description if k else "",
            "kind": k.kind if k else "", "verdict": e.verdict, "quote": e.quote, "quote_verified": e.quote_verified,
            "rationale": e.rationale, "span": list(span) if span else None,
        })
    order = {k.id: i for i, k in enumerate(c.job.criteria)}
    evals.sort(key=lambda x: order.get(x["criterion_id"], 99))
    return {
        **candidate_row(c),
        "job": {"id": c.job.id, "title": c.job.title},
        "profile": c.profile,
        "text": c.text_raw,
        "text_anon": c.text_anon,
        "hidden_text": c.hidden_text,
        "injection_evidence": c.injection_evidence,
        "evaluations": evals,
        "interview": interview_dict(c),
        "cost": candidate_costs(db, c.id),
        "history": history(db, c.id),
        "ai_proposal": ai_proposal(c),
        "decisions": [{"actor": d.actor, "decision": d.decision, "ai_proposed": d.ai_proposed, "comment": d.comment,
                       "override": d.ai_proposed in ("accept", "reject") and d.decision != d.ai_proposed,
                       "at": d.created_at.isoformat()} for d in c.decisions],
        "messages": [{"id": m.id, "kind": m.kind, "status": m.status} for m in c.messages],
        "interview_criteria": [
            {"id": k.id, "label": k.label, "description": k.description, "kind": k.kind}
            for k in c.job.criteria if k.source == "interview"
        ],
    }


@bp.post("/candidates/<int:cid>/reprocess")
@login_required
def reprocess(cid: int, user: str):
    db = get_session()
    c = db.get(Candidate, cid)
    if not c:
        raise HTTPException(404, "Candidat introuvable")
    c.status, c.error = "uploaded", ""
    db.commit()
    log_event(db, user, "cv_reprocess", "candidate", c.id)
    background(process_candidate, c.id)
    return {"ok": True}
