import re

from flask import Blueprint
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..audit import log_event
from ..costs import summarize
from ..llm import LLMError, llm
from ..models import Candidate, Criterion, Job, UsageEvent, now
from ..prompts import CRITERIA_SYSTEM, CRITERIA_USER
from ..schemas import CriteriaExtraction, CriterionEdit, CriterionIn, JobIn
from ..screening.pipeline import process_candidate
from ..util import aware
from ..web import HTTPException, background, login_required, parse
from ..web import db as get_session

bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")

# Defense in depth: never keep a criterion that targets a protected characteristic.
_BANNED = re.compile(
    r"(?<!\w)(âge|age|sexe|gender|photo\w*|nationalit\w*|origine|ethni\w*|situation familiale|enfants?|"
    r"religion|état de santé|handicap\w*|adresse|marital\w*)(?!\w)",
    re.I,
)


def _clean(criteria: list[CriterionIn]) -> list[CriterionIn]:
    return [c for c in criteria if not _BANNED.search(c.label)]


def extract_criteria(description: str, job_id: int | None = None) -> CriteriaExtraction:
    out = llm.structured(
        "smart", CRITERIA_SYSTEM, CRITERIA_USER.format(description=description), CriteriaExtraction,
        usage={"job_id": job_id, "purpose": "criteria"},
    )
    out.criteria = _clean(out.criteria)
    return out


def job_dict(job: Job, db: Session, with_description: bool = True) -> dict:
    counts = dict(
        db.execute(
            select(Candidate.triage, func.count()).where(Candidate.job_id == job.id).group_by(Candidate.triage)
        ).all()
    )
    total = sum(counts.values())
    stale = sum(
        1 for c in job.candidates
        if c.status == "screened" and (c.screened_at is None or aware(c.screened_at) < aware(job.criteria_updated_at or job.created_at))
    )
    d = {
        "stale": stale,
        "cost_total": round(summarize(db, job.id)["cost"]["total"], 6),
        "id": job.id,
        "title": job.title,
        "ref": job.ref,
        "created_at": job.created_at.isoformat(),
        "candidates": total,
        "counts": {"yes": counts.get("yes", 0), "maybe": counts.get("maybe", 0), "no": counts.get("no", 0)},
        "criteria": [
            {"id": c.id, "label": c.label, "description": c.description, "kind": c.kind, "source": c.source}
            for c in job.criteria
        ],
    }
    if with_description:
        d["description"] = job.description
    return d


def get_job_or_404(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Offre introuvable")
    return job


def set_criteria(db: Session, job: Job, items: list[CriterionIn | CriterionEdit]):
    """Upsert by id: edited criteria keep their id (and their candidates' evidence); removed ones go away."""
    existing = {c.id: c for c in job.criteria}
    keep: set[int] = set()
    changed = False
    for i, it in enumerate(items):
        cid = getattr(it, "id", 0)
        label, desc = it.label.strip(), it.description.strip()
        if cid in existing:
            c = existing[cid]
            if (c.label, c.description, c.kind, c.source) != (label, desc, it.kind, it.source):
                changed = True
            c.label, c.description, c.kind, c.source, c.position = label, desc, it.kind, it.source, i
            keep.add(cid)
        else:
            job.criteria.append(Criterion(label=label, description=desc, kind=it.kind, source=it.source, position=i))
            changed = True
    for cid, c in existing.items():
        if cid not in keep:
            job.criteria.remove(c)
            changed = True
    if changed:
        job.criteria_updated_at = now()
    db.flush()


def job_overview(job: Job) -> dict:
    """Pipeline funnel + the recruiter's to-do list for one offer (pure computation over what is stored)."""
    C = job.candidates
    screened = [c for c in C if c.status == "screened"]
    busy = [c for c in C if c.status in ("uploaded", "parsing", "screening")]
    failed = [c for c in C if c.status == "failed"]
    yes = [c for c in screened if c.triage == "yes"]
    sent_invite = lambda c: any(m.kind == "invite" and m.status == "sent" for m in c.messages)  # noqa: E731
    to_review = [c for c in screened if c.triage == "maybe" and not c.decision and not c.interview]
    invites_unsent = [c for c in screened if c.interview and c.interview.status == "pending" and not c.decision and not sent_invite(c)]
    waiting_candidate = [c for c in screened if c.interview and c.interview.status in ("pending", "started") and sent_invite(c) and not c.decision]
    to_decide = [c for c in screened if c.interview and c.interview.status == "scored" and not c.decision]
    rej_to_validate = [c for c in screened if c.triage == "no" and not c.decision]
    drafts = [m for c in C for m in c.messages if m.status == "draft" and m.kind != "invite"]
    interviewed = [c for c in screened if c.interview and c.interview.status in ("ended", "scored")]
    decided = [c for c in C if c.decision]
    replied = {m.candidate_id for c in C for m in c.messages if m.kind in ("acceptance", "rejection") and m.status == "sent"}
    base = f"/jobs/{job.id}"
    todo = []

    def add(key, n, label, cta, link=None, action=None, tone="warn"):
        if n:
            todo.append({"key": key, "count": n, "label": label, "cta": cta, "link": link, "action": action, "tone": tone})

    add("to_decide", len(to_decide), "pré-entretien(s) terminé(s) : à lire et à décider", "Lire et décider", f"{base}/candidates?filter=todecide")
    add("to_review", len(to_review), "candidat(s) « à examiner » (profil partiel)", "Examiner", f"{base}/candidates?filter=review")
    add("invites_unsent", len(invites_unsent), "invitation(s) au pré-entretien à envoyer", "Relire et envoyer", f"{base}/outbox")
    add("rejections", len(rej_to_validate), "refus proposé(s) par l'IA, à valider", "Valider en lot", action="reject-batch", tone="bad")
    add("drafts", len(drafts), "courrier(s) de réponse à relire et envoyer", "Ouvrir les courriers", f"{base}/outbox")
    add("failed", len(failed), "CV illisible(s) ou en erreur", "Voir", f"{base}/candidates?filter=failed", tone="bad")
    add("busy", len(busy), "CV en cours d'analyse…", "Suivre", f"{base}/candidates", tone="info")
    add("waiting", len(waiting_candidate), "candidat(s) invité(s), en attente de leur pré-entretien", "Voir", f"{base}/candidates?filter=waiting", tone="info")
    return {
        "funnel": {"received": len(C), "analyzed": len(screened), "prequalified": len(yes), "interviewed": len(interviewed),
                   "accepted": sum(1 for c in C if c.decision == "accepted"), "replied": len(replied)},
        "counts": {"busy": len(busy), "failed": len(failed), "yes": len(yes), "maybe": sum(1 for c in screened if c.triage == "maybe"),
                   "no": sum(1 for c in screened if c.triage == "no"), "decided": len(decided)},
        "todo": todo, "todo_count": sum(t["count"] for t in todo if t["tone"] != "info"),
    }


@bp.get("/<int:job_id>/overview")
@login_required
def get_overview(job_id: int, user: str):
    db = get_session()
    return job_overview(get_job_or_404(db, job_id))


@bp.get("")
@login_required
def list_jobs(user: str):
    db = get_session()
    jobs = db.scalars(select(Job).order_by(Job.id.desc())).all()
    return [{**job_dict(j, db, with_description=False), "todo_count": job_overview(j)["todo_count"]} for j in jobs]


@bp.post("")
@login_required
def create_job(user: str):
    db, body = get_session(), parse(JobIn)
    if len(body.description.strip()) < 40:
        raise HTTPException(400, "Collez la fiche de poste complète (texte trop court).")
    job = Job(title=body.title.strip() or "Nouvelle offre", ref=body.ref.strip(), description=body.description)
    db.add(job)
    db.commit()  # the job exists first so that the extraction cost is attributed to it
    try:
        ex = extract_criteria(body.description, job.id)
    except LLMError as e:
        db.delete(job)
        db.commit()
        raise HTTPException(502, str(e)) from e
    job.title = body.title.strip() or ex.title
    job.ref = body.ref.strip() or ex.ref
    set_criteria(db, job, ex.criteria)
    db.commit()
    log_event(db, "IA", "criteria_extracted", "job", job.id, count=len(ex.criteria))
    log_event(db, user, "job_created", "job", job.id, title=job.title)
    return job_dict(job, db)


@bp.get("/<int:job_id>")
@login_required
def get_job(job_id: int, user: str):
    db = get_session()
    return job_dict(get_job_or_404(db, job_id), db)


@bp.put("/<int:job_id>/criteria")
@login_required
def update_criteria(job_id: int, user: str):
    db, items = get_session(), parse(list[CriterionEdit], default=[])
    job = get_job_or_404(db, job_id)
    items = _clean(items)
    if not items:
        raise HTTPException(400, "Au moins un critère est requis.")
    set_criteria(db, job, items)
    db.commit()
    log_event(db, user, "criteria_edited", "job", job.id, count=len(items))
    return job_dict(job, db)


@bp.post("/<int:job_id>/rescreen")
@login_required
def rescreen(job_id: int, user: str):
    db = get_session()
    job = get_job_or_404(db, job_id)
    ids = [c.id for c in job.candidates if c.status in ("screened", "failed")]
    for c in job.candidates:
        if c.id in ids:
            c.status = "uploaded"
    db.commit()
    for cid in ids:
        background(process_candidate, cid)
    log_event(db, user, "job_rescreen", "job", job.id, candidates=len(ids))
    return {"count": len(ids)}


@bp.post("/<int:job_id>/re-extract")
@login_required
def re_extract(job_id: int, user: str):
    db = get_session()
    job = get_job_or_404(db, job_id)
    try:
        ex = extract_criteria(job.description, job.id)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    job.criteria.clear()  # new criteria = new ids: old evidence no longer applies, re-screen everything
    db.flush()
    set_criteria(db, job, ex.criteria)
    job.criteria_updated_at = now()
    ids = [c.id for c in job.candidates if c.status in ("screened", "failed")]
    for c in job.candidates:
        if c.id in ids:
            c.status = "uploaded"
    db.commit()
    log_event(db, "IA", "criteria_extracted", "job", job.id, count=len(ex.criteria), rescreened=len(ids))
    for cid in ids:
        background(process_candidate, cid)
    return job_dict(job, db)


@bp.delete("/<int:job_id>")
@login_required
def delete_job(job_id: int, user: str):
    db = get_session()
    job = get_job_or_404(db, job_id)
    title = job.title
    # One statement; the database cascades to criteria, candidates and everything attached to them
    # (foreign keys ON DELETE CASCADE, enforced by PRAGMA foreign_keys in db.py).
    db.execute(delete(Job).where(Job.id == job_id))
    # The cost lines carry the offer number but no foreign key. SQLite reuses the number of a deleted offer, so
    # leaving them would make the next offer inherit this offer's costs: an offer's costs go with it.
    db.execute(delete(UsageEvent).where(UsageEvent.job_id == job_id))
    db.commit()
    log_event(db, user, "job_deleted", "job", job_id, title=title)
    return {"ok": True}
