"""Cost tracking. Every LLM call and every voice call is recorded with its real usage and cost (USD)."""
import logging

from sqlalchemy import func, select

from .db import SessionLocal
from .models import UsageEvent

log = logging.getLogger("costs")

# Anthropic list prices, USD per 1M tokens (input, output). Thinking tokens are billed as output (already in output_tokens).
PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (2.0, 10.0), "claude-sonnet-5": (2.0, 10.0), "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-5-5": (0.10, 0.50), "claude-haiku-4-5": (1.0, 5.0),
    "claude-opus-5-5": (4.0, 20.0), "claude-opus-5": (5.0, 25.0), "claude-opus-4-8": (5.0, 25.0),
    "claude-fable-5-1": (10.0, 50.0), "claude-fable-5": (10.0, 50.0),
}
FALLBACK_PRICE = (2.0, 10.0)
VOICE_USD_PER_MIN = 0.08  # only used if ElevenLabs does not report cost_fiat

# purpose -> (group, French label). Groups drive the dashboard.
PURPOSES: dict[str, tuple[str, str]] = {
    "transcribe": ("cv", "Lecture d'un CV scanné"),
    "profile": ("cv", "Extraction du profil (contacts, parcours)"),
    "injection": ("cv", "Détection d'injection"),
    "evaluate": ("cv", "Évaluation sur les critères"),
    "plan": ("interview", "Plan de questions du pré-entretien"),
    "interview_chat": ("interview", "Dialogue (mode écrit)"),
    "score": ("interview", "Notation et synthèse"),
    "voice_call": ("voice", "Appel vocal (ElevenLabs)"),
    "criteria": ("other", "Extraction des critères de l'offre"),
    "draft_invite": ("other", "Courrier : invitation"),
    "draft_rejection": ("other", "Courrier : refus"),
    "draft_acceptance": ("other", "Courrier : rendez-vous"),
}
GROUP_LABELS = {"cv": "Analyse des CV", "interview": "Pré-entretien (IA)", "voice": "Voix (ElevenLabs)", "other": "Critères et courriers"}
GROUPS = list(GROUP_LABELS)


def group_of(purpose: str) -> str:
    return PURPOSES.get(purpose, ("other", purpose))[0]


def llm_cost(model: str, input_tokens: int, output_tokens: int) -> tuple[float, bool]:
    """Returns (cost_usd, exact). exact=False when the model is not in the price table."""
    price = PRICING.get(model)
    if model == "claude-haiku-5-5" and input_tokens > 100_000:  # long-prompt tier
        price = (0.50, 2.50)
    exact = price is not None
    pin, pout = price or FALLBACK_PRICE
    return (input_tokens * pin + output_tokens * pout) / 1_000_000, exact


def record(provider: str, purpose: str, *, model: str = "", job_id: int | None = None, candidate_id: int | None = None,
           input_tokens: int = 0, output_tokens: int = 0, cost_usd: float = 0.0, ref: str = "", meta: dict | None = None):
    """Never raises: cost tracking must not break the app."""
    try:
        with SessionLocal() as db:
            db.add(UsageEvent(provider=provider, model=model, purpose=purpose, job_id=job_id, candidate_id=candidate_id,
                              input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost_usd, ref=ref, meta=meta or {}))
            db.commit()
    except Exception:  # noqa: BLE001
        log.exception("could not record usage")


def record_llm(model: str, usage, ctx: dict | None):
    if not ctx:
        return
    tin, tout = getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0
    cost, exact = llm_cost(model, tin, tout)
    record("anthropic", ctx.get("purpose", "other"), model=model, job_id=ctx.get("job_id"), candidate_id=ctx.get("candidate_id"),
           input_tokens=tin, output_tokens=tout, cost_usd=cost, meta={} if exact else {"estimated_price": True})


def record_voice(conv: dict, job_id: int | None, candidate_id: int | None):
    """ElevenLabs reports the real dollar cost of the call (metadata.cost_fiat) plus its LLM share: use it."""
    cid = conv.get("conversation_id", "")
    with SessionLocal() as db:
        if cid and db.scalar(select(UsageEvent.id).where(UsageEvent.provider == "elevenlabs", UsageEvent.ref == cid)):
            return  # already recorded (re-fetch)
    m = conv.get("metadata") or {}
    secs = float(m.get("call_duration_secs") or 0)
    fiat = m.get("cost_fiat")
    estimated = fiat is None
    cost = float(fiat) if fiat is not None else secs / 60 * VOICE_USD_PER_MIN
    ch = m.get("charging") or {}
    record("elevenlabs", "voice_call", model="elevenlabs-agent", job_id=job_id, candidate_id=candidate_id, cost_usd=cost, ref=cid,
           meta={"duration_secs": secs, "credits": m.get("cost"), "llm_price": ch.get("llm_price"),
                 "platform_price": ch.get("platform_price"), "estimated": estimated})


# ------------------------------------------------------------------ aggregation
def _empty() -> dict:
    return {g: 0.0 for g in GROUPS} | {"total": 0.0}


def summarize(db, job_id: int | None = None) -> dict:
    """Totals per group + per-unit averages, for one job or everything."""
    q = select(UsageEvent.purpose, UsageEvent.candidate_id, func.sum(UsageEvent.cost_usd), func.count(),
               func.sum(UsageEvent.input_tokens), func.sum(UsageEvent.output_tokens))
    if job_id is not None:
        q = q.where(UsageEvent.job_id == job_id)
    rows = db.execute(q.group_by(UsageEvent.purpose, UsageEvent.candidate_id)).all()
    cost, calls, tin, tout = _empty(), 0, 0, 0
    cv_cands, iv_cands = set(), set()
    for purpose, cand, c, n, i, o in rows:
        g = group_of(purpose)
        cost[g] += c or 0
        cost["total"] += c or 0
        calls += n
        tin += i or 0
        tout += o or 0
        if cand is not None and g == "cv":
            cv_cands.add(cand)
        if cand is not None and g in ("interview", "voice"):
            iv_cands.add(cand)
    iv_cost = cost["interview"] + cost["voice"]
    return {
        "cost": {k: round(v, 6) for k, v in cost.items()}, "calls": calls, "input_tokens": tin, "output_tokens": tout,
        "cv_analyzed": len(cv_cands), "interviews": len(iv_cands),
        "per_cv": round(cost["cv"] / len(cv_cands), 6) if cv_cands else 0.0,
        "per_interview": round(iv_cost / len(iv_cands), 6) if iv_cands else 0.0,
    }
