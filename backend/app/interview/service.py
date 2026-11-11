"""Pre-interview: plan, agent prompt, text chat engine, scoring + synthesis."""
import logging
import secrets
import threading
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import log_event
from ..config import settings
from ..db import SessionLocal
from ..llm import LLMError, llm
from ..models import Candidate, Interview, now
from ..prompts import (
    AGENT_END_TEXT,
    AGENT_PROMPT_TEMPLATE,
    PLAN_SYSTEM,
    PLAN_USER,
    PROMPT_VERSION,
    SCORE_SYSTEM,
    SCORE_USER,
)
from ..schemas import InterviewPlan, Synthesis
from ..screening.triage import KIND_WEIGHT  # same must/nice weights as the CV score
from ..screening.verify import verify_quote

log = logging.getLogger("interview")

LANG_NAMES = {"fr": "français", "en": "English"}
MAX_TURNS = 40
GRADE_MAX = 3.0
CV_WEIGHT = 0.4  # global = 0.4*cv + 0.6*interview


def interview_language(c: Candidate) -> str:
    return "en" if (c.lang or "fr").startswith("en") else "fr"


def first_name(c: Candidate) -> str:
    name = (c.profile or {}).get("name", "").strip()
    return name.split()[0].title() if name else ""


def _criteria_block(c: Candidate) -> str:
    return "\n".join(
        f"- id={k.id} [{'INDISPENSABLE' if k.kind == 'must' else 'souhaité'} | source={k.source}] {k.label}: {k.description}"
        for k in c.job.criteria
    )


def build_plan(c: Candidate, language: str) -> dict:
    by_id = {k.id: k for k in c.job.criteria}
    verdicts = "\n".join(
        f"- id={e.criterion_id} {by_id[e.criterion_id].label}: {e.verdict} — {e.rationale}"
        for e in c.evaluations if e.criterion_id in by_id
    ) or "(aucun)"
    plan = llm.structured(
        "smart", PLAN_SYSTEM,
        PLAN_USER.format(title=c.job.title, language=LANG_NAMES[language], criteria=_criteria_block(c), verdicts=verdicts),
        InterviewPlan, max_tokens=3000, usage={"job_id": c.job_id, "candidate_id": c.id, "purpose": "plan"},
    )
    return plan.model_dump()


_guard = threading.Lock()
_locks: dict[tuple, threading.Lock] = {}


def _lock(kind: str, cid: int) -> threading.Lock:
    """One lock per (step, candidate): concurrent clicks and the background preparation can never create things twice,
    and the slow AI step (the plan) never blocks the instant step (the link)."""
    with _guard:
        return _locks.setdefault((kind, cid), threading.Lock())


def has_plan(iv: Interview) -> bool:
    return bool((iv.plan or {}).get("questions"))


def create_interview(db: Session, c: Candidate) -> Interview:
    """INSTANT (no AI call): the interview row, the unique token and the deadline. Idempotent and race-safe."""
    with _lock("create", c.id):
        db.refresh(c)
        if c.interview:
            return c.interview
        iv = Interview(candidate_id=c.id, plan={}, language=interview_language(c), expires_at=now() + timedelta(days=settings.interview_valid_days))
        db.add(iv)
        c.token = c.token or secrets.token_urlsafe(24)
        try:
            db.commit()
        except IntegrityError:  # another request created it first: use that one
            db.rollback()
    db.refresh(c)
    return c.interview


def ensure_plan(db: Session, c: Candidate) -> Interview:
    """Build the question plan once (a second caller waits for the first instead of paying for a second AI call)."""
    iv = c.interview
    if has_plan(iv):
        return iv
    with _lock("plan", c.id):
        db.refresh(iv)
        if has_plan(iv):
            return iv
        plan = build_plan(c, iv.language)
        iv.plan = plan
        db.commit()
        log_event(db, "IA", "interview_plan_built", "candidate", c.id, questions=len(plan["questions"]), prompt_version=PROMPT_VERSION)
    return iv


def ensure_invite_draft(db: Session, c: Candidate):
    """The invitation e-mail draft, created once (a draft that already exists is reused)."""
    from ..comms import draft_message
    with _lock("draft", c.id):
        db.refresh(c)
        existing = next((m for m in reversed(c.messages) if m.kind == "invite" and m.status == "draft"), None)
        return existing or draft_message(db, c, "invite")


def prepare_assets(db: Session, c: Candidate):
    """Everything that needs the AI and can wait: the plan and, if no invitation exists yet, its draft."""
    ensure_plan(db, c)
    if not any(m.kind == "invite" for m in c.messages):
        try:
            ensure_invite_draft(db, c)
        except Exception as e:  # noqa: BLE001
            log.warning("invite draft failed for %s: %s", c.id, e)


def prepare_assets_bg(candidate_id: int):
    """Background task wrapper (own session)."""
    with SessionLocal() as db:
        try:
            c = db.get(Candidate, candidate_id)
            if c and c.interview:
                prepare_assets(db, c)
        except Exception:  # noqa: BLE001
            log.exception("preparing the interview failed for %s", candidate_id)


def ensure_interview(db: Session, c: Candidate) -> Interview:
    """Full preparation, synchronous (used by the pipeline for pre-qualified candidates, which already runs in the background)."""
    iv = create_interview(db, c)
    prepare_assets(db, c)
    return iv


def plan_text(plan: dict) -> str:
    return "\n".join(f"{i + 1}. [{q['kind']}] {q['question']}  (à écouter: {q['listen_for']})" for i, q in enumerate(plan.get("questions", [])))


def first_message(name: str, lang: str) -> str:
    if lang == "en":
        return (f"Hi{' ' + name if name else ''}, this is Camille, the AI assistant for Orvane's recruiting team. "
                "We'll chat for about ten minutes. It's recorded, and a recruiter will read it and make the decision. Is now a good time?")
    return (f"Bonjour{' ' + name if name else ''}, ici Camille, l'assistante IA du recrutement d'Orvane. "
            "On va échanger une dizaine de minutes. C'est enregistré, et c'est un recruteur qui lira l'échange et décidera. Ça vous va, c'est un bon moment ?")


def agent_variables(c: Candidate, iv: Interview) -> dict:
    return {
        "first_message": first_message(first_name(c), iv.language),
        "job_title": c.job.title,
        "candidate_first_name": first_name(c) or ("vous" if iv.language == "fr" else "there"),
        "language_name": LANG_NAMES.get(iv.language, "français"),
        "plan": plan_text(iv.plan),
    }


def render_agent_prompt(vars_: dict, text_mode: bool = False) -> str:
    out = AGENT_PROMPT_TEMPLATE
    for k, v in vars_.items():
        out = out.replace("{{" + k + "}}", v)
    return out + ("\n\n" + AGENT_END_TEXT if text_mode else "")


# ---------------------------------------------------------------- text chat
def _messages(iv: Interview) -> list[dict]:
    msgs = [{"role": "user", "content": "[Le candidat vient d'arriver, commence l'entretien.]"}]
    for t in iv.transcript:
        msgs.append({"role": "assistant" if t["role"] == "agent" else "user", "content": t["text"]})
    return msgs


def agent_turn(c: Candidate, iv: Interview) -> tuple[str, bool]:
    system = render_agent_prompt(agent_variables(c, iv), text_mode=True)
    reply = llm.chat("fast", system, _messages(iv), max_tokens=500,
                     usage={"job_id": c.job_id, "candidate_id": c.id, "purpose": "interview_chat"})
    done = "[FIN]" in reply
    reply = reply.replace("[FIN]", "").strip()
    if len([t for t in iv.transcript if t["role"] == "candidate"]) >= MAX_TURNS:
        done = True
    return reply, done


# ---------------------------------------------------------------- scoring
def transcript_text(transcript: list[dict]) -> str:
    return "\n".join(f"{'ASSISTANTE' if t['role'] == 'agent' else 'CANDIDAT'}: {t['text']}" for t in transcript)


def candidate_text(transcript: list[dict]) -> str:
    return "\n".join(t["text"] for t in transcript if t["role"] != "agent")


def interview_note(grades: dict[int, int], criteria) -> float:
    """0..10 from per-criterion grades (0-3), weighted must=3 / nice=1. Criteria not covered (-1/absent) are excluded."""
    assessed = [k for k in criteria if grades.get(k.id, -1) >= 0]
    tot = sum(KIND_WEIGHT[k.kind] for k in assessed)
    if not tot:
        return 0.0
    return 10 * sum(KIND_WEIGHT[k.kind] * min(GRADE_MAX, grades[k.id]) / GRADE_MAX for k in assessed) / tot


def score_interview(candidate_id: int):
    db = SessionLocal()
    try:
        c = db.get(Candidate, candidate_id)
        iv = c.interview
        if not iv or not iv.transcript:
            return
        spoken = [t for t in iv.transcript if t["role"] != "agent"]
        if not spoken:
            iv.status, iv.synthesis = "ended", {"empty": True}
            db.commit()
            return
        syn = llm.structured(
            "smart", SCORE_SYSTEM,
            SCORE_USER.format(title=c.job.title, criteria=_criteria_block(c), cv_summary=c.summary or "-",
                              transcript=transcript_text(iv.transcript)),
            Synthesis, max_tokens=5000, usage={"job_id": c.job_id, "candidate_id": c.id, "purpose": "score"},
        )
        said = candidate_text(iv.transcript)
        grades: dict[int, int] = {}
        out_grades = []
        valid = {k.id for k in c.job.criteria}
        for g in syn.grades:
            if g.criterion_id not in valid:
                continue
            gr, note = max(-1, min(3, g.grade)), g.rationale
            if gr > 0:  # no quote, no grade: unverified = "not assessed" (excluded), never "contradicted" (0)
                ok, _ = verify_quote(g.quote, said, fuzzy=0.85)
                if not ok:
                    note, gr = f"[citation non vérifiée, note initiale {g.grade}] {note}", -1
            grades[g.criterion_id] = gr
            out_grades.append({"criterion_id": g.criterion_id, "grade": gr, "quote": g.quote if gr > 0 else "", "rationale": note})

        def ev(items):
            res = []
            for e in items:
                ok = bool(e.quote) and verify_quote(e.quote, said, fuzzy=0.85)[0]
                res.append({"text": e.text, "quote": e.quote if ok else "", "verified": ok})
            return res

        note = interview_note(grades, c.job.criteria)
        iv.scores = {"grades": out_grades, "note": round(note, 2)}
        iv.synthesis = {
            "strengths": ev(syn.strengths), "doubts": ev(syn.doubts), "probes": syn.probes,
            "logistics": [l.model_dump() for l in syn.logistics], "blockers": syn.blockers,
            "discrepancies": syn.discrepancies, "recommendation": syn.recommendation,
            "headline": syn.headline, "manipulation": syn.manipulation,
        }
        iv.status = "scored"
        c.interview_note = round(note, 2)
        cv = c.cv_score if c.cv_score is not None else 0.0
        c.global_score = round(CV_WEIGHT * cv + (1 - CV_WEIGHT) * note / 10, 3)
        db.commit()
        log_event(db, "IA", "interview_scored", "candidate", c.id, note=round(note, 1),
                  recommendation=syn.recommendation, prompt_version=PROMPT_VERSION)
    except (LLMError, Exception) as e:  # noqa: BLE001
        log.exception("scoring failed for %s", candidate_id)
        c = db.get(Candidate, candidate_id)
        if c and c.interview:
            c.interview.synthesis = {"error": str(e)[:300]}
            c.interview.status = "ended"
            db.commit()
    finally:
        db.close()
