from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import costs as C
from ..auth import current_user
from ..db import get_db
from ..models import Candidate, Job, UsageEvent
from .jobs import get_job_or_404

router = APIRouter(prefix="/api/costs", tags=["costs"])


@router.get("")
def overview(db: Session = Depends(get_db), user: str = Depends(current_user)):
    jobs = db.scalars(select(Job).order_by(Job.id.desc())).all()
    rows = []
    for j in jobs:
        s = C.summarize(db, j.id)
        rows.append({"id": j.id, "title": j.title, "ref": j.ref, "candidates": len(j.candidates), **s})
    everything = C.summarize(db)
    listed = sum(r["cost"]["total"] for r in rows)
    return {
        "total": everything["cost"]["total"], "calls": everything["calls"], "group_labels": C.GROUP_LABELS,
        "per_cv": everything["per_cv"], "per_interview": everything["per_interview"],
        "cv_analyzed": everything["cv_analyzed"], "interviews": everything["interviews"],
        "cost": everything["cost"], "deleted_or_unassigned": round(max(0.0, everything["cost"]["total"] - listed), 6),
        "jobs": rows,
    }


@router.get("/jobs/{job_id}")
def job_detail(job_id: int, db: Session = Depends(get_db), user: str = Depends(current_user)):
    job = get_job_or_404(db, job_id)
    s = C.summarize(db, job.id)
    purposes = db.execute(
        select(UsageEvent.purpose, UsageEvent.provider, UsageEvent.model, func.count(), func.sum(UsageEvent.input_tokens),
               func.sum(UsageEvent.output_tokens), func.sum(UsageEvent.cost_usd))
        .where(UsageEvent.job_id == job.id).group_by(UsageEvent.purpose, UsageEvent.provider, UsageEvent.model)
    ).all()
    by_purpose = sorted(
        [{"purpose": p, "label": C.PURPOSES.get(p, ("other", p))[1], "group": C.group_of(p), "provider": pr, "model": m,
          "calls": n, "input_tokens": i or 0, "output_tokens": o or 0, "cost": round(c or 0, 6)} for p, pr, m, n, i, o, c in purposes],
        key=lambda r: -r["cost"])
    per_cand: dict[int, dict] = {}
    for cand, purpose, cost in db.execute(select(UsageEvent.candidate_id, UsageEvent.purpose, func.sum(UsageEvent.cost_usd))
                                          .where(UsageEvent.job_id == job.id, UsageEvent.candidate_id.is_not(None))
                                          .group_by(UsageEvent.candidate_id, UsageEvent.purpose)).all():
        d = per_cand.setdefault(cand, C._empty())
        d[C.group_of(purpose)] += cost or 0
        d["total"] += cost or 0
    names = {c.id: c for c in job.candidates}
    candidates = sorted(
        [{"id": cid, "name": ((names[cid].profile or {}).get("name") or names[cid].filename) if cid in names else f"#{cid}",
          "triage": names[cid].triage if cid in names else "", "cost": {k: round(v, 6) for k, v in d.items()}}
         for cid, d in per_cand.items()], key=lambda r: -r["cost"]["total"])
    drafts = [r for r in by_purpose if r["purpose"].startswith("draft_")]
    n_drafts, c_drafts = sum(r["calls"] for r in drafts), sum(r["cost"] for r in drafts)
    screened = [c for c in job.candidates if c.status == "screened"]
    yes_rate = (sum(1 for c in screened if c.triage == "yes") / len(screened)) if screened else None
    return {
        "job": {"id": job.id, "title": job.title, "ref": job.ref}, "group_labels": C.GROUP_LABELS, **s,
        "by_purpose": by_purpose, "candidates": candidates, "voice_minutes": round(sum(
            (e.meta or {}).get("duration_secs", 0) for e in db.scalars(select(UsageEvent).where(
                UsageEvent.job_id == job.id, UsageEvent.purpose == "voice_call")).all()) / 60, 2),
        "forecast": {"avg_cv": s["per_cv"], "avg_interview": s["per_interview"], "avg_reply": round(c_drafts / n_drafts, 6) if n_drafts else 0.0,
                     "yes_rate": yes_rate, "sample_cv": s["cv_analyzed"], "sample_interviews": s["interviews"]},
    }
