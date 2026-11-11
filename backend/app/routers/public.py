"""Candidate-facing endpoints. No account: the unguessable token is the credential."""
from datetime import UTC, datetime

from flask import Blueprint
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import log_event
from ..config import settings
from ..interview.elevenlabs import ElevenLabsError, fetch_and_score, signed_url
from ..interview.service import (
    agent_turn,
    agent_variables,
    ensure_plan,
    score_interview,
)
from ..models import Candidate, Interview
from ..util import aware, format_date
from ..web import HTTPException, background, parse
from ..web import db as get_session

bp = Blueprint("public", __name__, url_prefix="/api/public/interview")


def _load(db: Session, token: str) -> tuple[Candidate, Interview]:
    if not token or len(token) < 20:
        raise HTTPException(404, "Lien invalide")
    c = db.scalar(select(Candidate).where(Candidate.token == token))
    if not c or not c.interview:
        raise HTTPException(404, "Lien invalide ou expiré")
    return c, c.interview


def _now():
    return datetime.now(UTC)


def _expired(iv: Interview) -> bool:
    return bool(iv.expires_at) and _now() > aware(iv.expires_at) and iv.status in ("pending", "started")


def _open(iv: Interview):
    """Closed (410) once the deadline has passed, unless the interview is already finished."""
    if _expired(iv):
        raise HTTPException(410, "Ce lien a expiré. Contactez l'équipe de recrutement pour en recevoir un nouveau.")


def _t(role: str, text: str) -> dict:
    return {"role": role, "text": text, "ts": _now().isoformat()}


@bp.get("/<token>")
def info(token: str):
    db = get_session()
    c, iv = _load(db, token)
    name = ((c.profile or {}).get("name") or "").split()
    return {
        "first_name": name[0].title() if name else "",
        "job_title": c.job.title,
        "language": iv.language,
        "expired": _expired(iv),
        "expires_at": iv.expires_at.isoformat() if iv.expires_at else None,
        "expires_label": format_date(iv.expires_at, iv.language),
        "status": iv.status,
        "consented": iv.consent_at is not None,
        "mode": iv.mode,
        "voice_available": bool(settings.elevenlabs_api_key and settings.elevenlabs_agent_id),
        "transcript": iv.transcript if iv.status == "started" and iv.mode == "text" else [],
    }


class ConsentIn(BaseModel):
    language: str = "fr"
    mode: str = "text"  # text | voice


@bp.post("/<token>/consent")
def consent(token: str):
    db, body = get_session(), parse(ConsentIn)
    c, iv = _load(db, token)
    if iv.status in ("ended", "scored"):
        raise HTTPException(409, "Cet entretien est déjà terminé.")
    _open(iv)
    ensure_plan(db, c)   # normally ready already (built in the background); waits if the link was opened within seconds
    iv.language = body.language if body.language in ("fr", "en") else iv.language
    iv.mode = body.mode if body.mode in ("text", "voice") else "text"
    iv.consent_at = iv.consent_at or _now()
    iv.status = "started" if iv.status == "pending" else iv.status
    db.commit()
    log_event(db, "candidat", "interview_consent", "candidate", c.id, mode=iv.mode, language=iv.language)
    return {"ok": True, "mode": iv.mode, "language": iv.language}


@bp.post("/<token>/start")
def start_text(token: str):
    db = get_session()
    c, iv = _load(db, token)
    if not iv.consent_at:
        raise HTTPException(400, "Consentement requis.")
    if iv.status in ("ended", "scored"):
        raise HTTPException(409, "Cet entretien est déjà terminé.")
    _open(iv)
    ensure_plan(db, c)
    if not iv.transcript:
        reply, _ = agent_turn(c, iv)
        iv.transcript = [_t("agent", reply)]
        iv.mode = "text"
        db.commit()
    return {"transcript": iv.transcript}


class MsgIn(BaseModel):
    text: str


@bp.post("/<token>/message")
def message(token: str):
    db, body = get_session(), parse(MsgIn)
    c, iv = _load(db, token)
    if not iv.consent_at:  # nothing is recorded before the candidate has agreed
        raise HTTPException(400, "Consentement requis.")
    if iv.status in ("ended", "scored"):
        raise HTTPException(409, "Cet entretien est déjà terminé.")
    _open(iv)
    text = body.text.strip()[:2000]
    if not text:
        raise HTTPException(400, "Message vide.")
    iv.transcript = [*iv.transcript, _t("candidate", text)]
    db.commit()
    reply, done = agent_turn(c, iv)
    iv.transcript = [*iv.transcript, _t("agent", reply)]
    if done:
        iv.status = "ended"
    db.commit()
    if done:
        log_event(db, "candidat", "interview_ended", "candidate", c.id, mode="text")
        background(score_interview, c.id)
    return {"reply": reply, "done": done}


@bp.post("/<token>/finish")
def finish(token: str):
    db = get_session()
    c, iv = _load(db, token)
    if not iv.consent_at:
        raise HTTPException(400, "Consentement requis.")
    if iv.status not in ("ended", "scored"):
        iv.status = "ended"
        db.commit()
        log_event(db, "candidat", "interview_ended", "candidate", c.id, mode=iv.mode)
        background(score_interview, c.id)
    return {"ok": True}


@bp.get("/<token>/voice-session")
def voice_session(token: str):
    db = get_session()
    c, iv = _load(db, token)
    if not iv.consent_at:
        raise HTTPException(400, "Consentement requis.")
    if iv.status in ("ended", "scored"):
        raise HTTPException(409, "Cet entretien est déjà terminé.")
    _open(iv)
    ensure_plan(db, c)
    try:
        url = signed_url()
    except ElevenLabsError as e:
        raise HTTPException(503, str(e)) from e
    iv.mode = "voice"
    db.commit()
    return {"signed_url": url, "language": iv.language, "dynamic_variables": agent_variables(c, iv)}


class VoiceEnd(BaseModel):
    conversation_id: str


@bp.post("/<token>/voice-ended")
def voice_ended(token: str):
    db, body = get_session(), parse(VoiceEnd)
    c, iv = _load(db, token)
    if iv.status not in ("ended", "scored"):
        iv.el_conversation_id = body.conversation_id[:100]
        iv.mode = "voice"
        iv.status = "ended"
        db.commit()
        log_event(db, "candidat", "interview_ended", "candidate", c.id, mode="voice", conversation=iv.el_conversation_id)
        background(fetch_and_score, c.id)
    return {"ok": True}
