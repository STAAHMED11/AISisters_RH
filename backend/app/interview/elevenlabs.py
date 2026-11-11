"""ElevenLabs Agents: private signed URLs + transcript retrieval by polling (no public webhook needed)."""
import logging
import time

import httpx

from .. import costs
from ..config import settings
from ..db import SessionLocal
from ..models import Candidate
from .service import score_interview

log = logging.getLogger("elevenlabs")
BASE = "https://api.elevenlabs.io/v1/convai"


class ElevenLabsError(Exception):
    pass


def _headers() -> dict:
    if not (settings.elevenlabs_api_key and settings.elevenlabs_agent_id):
        raise ElevenLabsError("ElevenLabs n'est pas configuré (ELEVENLABS_API_KEY / ELEVENLABS_AGENT_ID).")
    return {"xi-api-key": settings.elevenlabs_api_key}


def signed_url() -> str:
    r = httpx.get(f"{BASE}/conversation/get-signed-url", params={"agent_id": settings.elevenlabs_agent_id},
                  headers=_headers(), timeout=20)
    if not r.is_success:
        raise ElevenLabsError(f"ElevenLabs a refusé la session ({r.status_code}): {r.text[:200]}")
    return r.json()["signed_url"]


def fetch_conversation(conversation_id: str) -> dict:
    r = httpx.get(f"{BASE}/conversations/{conversation_id}", headers=_headers(), timeout=30)
    if not r.is_success:
        raise ElevenLabsError(f"conversation introuvable ({r.status_code})")
    return r.json()


def to_transcript(conv: dict) -> list[dict]:
    out = []
    for t in conv.get("transcript") or []:
        text = (t.get("message") or "").strip()
        if not text:  # tool calls etc.
            continue
        out.append({"role": "agent" if t.get("role") == "agent" else "candidate", "text": text,
                    "t": t.get("time_in_call_secs")})
    return out


def fetch_and_score(candidate_id: int, wait: int = 150):
    """Background: wait for ElevenLabs to finish processing the call, store the transcript, then score."""
    deadline = time.time() + wait
    db = SessionLocal()
    try:
        c = db.get(Candidate, candidate_id)
        iv = c.interview
        conv = {}
        while time.time() < deadline:
            try:
                conv = fetch_conversation(iv.el_conversation_id)
            except ElevenLabsError as e:
                log.warning("fetch failed: %s", e)
                time.sleep(3)
                continue
            if conv.get("status") in ("done", "failed") and conv.get("transcript"):
                costs.record_voice(conv, c.job_id, c.id)  # real $ from ElevenLabs (deduplicated by conversation id)
                break
            time.sleep(3)
        tr = to_transcript(conv)
        if tr:
            iv.transcript = tr
            iv.status = "ended"
            db.commit()
    finally:
        db.close()
    score_interview(candidate_id)
