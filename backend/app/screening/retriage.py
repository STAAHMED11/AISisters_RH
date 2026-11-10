"""Re-apply the triage rules to already-screened candidates. Pure code over stored verdicts: no LLM call, instant.
Run at startup so that changing a threshold (YES_THRESHOLD / MAYBE_THRESHOLD) never leaves stale labels."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import log_event
from ..models import Candidate
from .triage import PREQUAL, triage

log = logging.getLogger("retriage")
CV_WEIGHT = 0.4  # keep in sync with interview.service (global = 0.4*cv + 0.6*interview)


def retriage_candidate(c: Candidate) -> tuple[str, str] | None:
    """Returns (old, new) triage if it changed."""
    kinds = {k.id: k for k in c.job.criteria}
    items = [(kinds[e.criterion_id].kind, e.verdict) for e in c.evaluations
             if e.criterion_id in kinds and kinds[e.criterion_id].source == "cv"]
    if not items:
        return None
    score, tri = triage(items, injection=c.injection_flag)
    old = c.triage
    c.cv_score, c.triage, c.prequal = score, tri, PREQUAL[tri]
    if c.interview_note is not None:
        c.global_score = round(CV_WEIGHT * score + (1 - CV_WEIGHT) * c.interview_note / 10, 3)
    return (old, tri) if old != tri else None


def retriage_all(db: Session) -> int:
    changed = 0
    for c in db.scalars(select(Candidate).where(Candidate.status == "screened")).all():
        r = retriage_candidate(c)
        if r:
            changed += 1
            log_event(db, "système", "retriage", "candidate", c.id, old=r[0], new=r[1])
    db.commit()
    if changed:
        log.info("re-triaged %s candidate(s) after a rule/threshold change", changed)
    return changed
