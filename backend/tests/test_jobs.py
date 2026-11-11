from backend.app import llm as llm_mod
from backend.app.routers.jobs import _clean
from backend.app.schemas import CriteriaExtraction, CriterionIn

FAKE = CriteriaExtraction(
    title="Responsable d'entrepôt", ref="ORV-1",
    criteria=[
        CriterionIn(label="Management ≥ 5 ans", description="équipes > 30", kind="must", source="cv"),
        CriterionIn(label="Disponibilité", kind="nice", source="interview"),
        CriterionIn(label="Âge entre 30 et 45 ans", kind="must", source="cv"),
        CriterionIn(label="Nationalité française", kind="must", source="cv"),
        CriterionIn(label="Hygiène santé sécurité", kind="must", source="cv"),
    ],
)


def _actions():
    from sqlalchemy import select

    from backend.app.db import SessionLocal
    from backend.app.models import AuditLog
    with SessionLocal() as db:
        return [a for a in db.scalars(select(AuditLog.action)).all()]

def test_clean_drops_protected_criteria():
    labels = [c.label for c in _clean(FAKE.criteria)]
    assert labels == ["Management ≥ 5 ans", "Disponibilité", "Hygiène santé sécurité"]


def test_job_lifecycle(client, monkeypatch):
    monkeypatch.setattr(llm_mod.llm, "structured", lambda *a, **k: FAKE.model_copy(deep=True))
    r = client.post("/api/jobs", json={"description": "x" * 60})
    assert r.status_code == 200, r.text
    job = r.get_json()
    assert job["title"] == "Responsable d'entrepôt" and len(job["criteria"]) == 3
    jid = job["id"]

    new = [{"label": "WMS", "description": "", "kind": "must", "source": "cv"}]
    r = client.put(f"/api/jobs/{jid}/criteria", json=new)
    assert [c["label"] for c in r.get_json()["criteria"]] == ["WMS"]
    assert client.put(f"/api/jobs/{jid}/criteria", json=[]).status_code == 400
    assert len(client.get("/api/jobs").get_json()) >= 1
    assert client.post("/api/jobs", json={"description": "court"}).status_code == 400
    actions = _actions()
    assert "criteria_edited" in actions and "job_created" in actions
    assert client.delete(f"/api/jobs/{jid}").status_code == 200
    assert client.get(f"/api/jobs/{jid}").status_code == 404


def test_editing_criteria_keeps_evidence_and_flags_stale(client, monkeypatch):
    """Regression: editing criteria must NOT wipe candidates' evaluations (ids are preserved)."""
    from backend.app.db import SessionLocal
    from backend.app.models import Candidate, Evaluation, now

    monkeypatch.setattr(llm_mod.llm, "structured", lambda *a, **k: FAKE.model_copy(deep=True))
    job = client.post("/api/jobs", json={"description": "x" * 60}).get_json()
    crit = job["criteria"]
    db = SessionLocal()
    c = Candidate(job_id=job["id"], filename="a.pdf", status="screened", screened_at=now())
    db.add(c); db.flush()
    for k in crit:
        db.add(Evaluation(candidate_id=c.id, criterion_id=k["id"], verdict="met", quote="q" * 10, quote_verified=True))
    db.commit()
    cid = c.id

    def n_evals():
        db.expire_all()
        return db.query(Evaluation).filter_by(candidate_id=cid).count()

    assert n_evals() == 3 and client.get(f"/api/jobs/{job['id']}").get_json()["stale"] == 0
    # no-op save (same content, ids sent back): evidence intact, nothing stale
    r = client.put(f"/api/jobs/{job['id']}/criteria", json=crit)
    assert n_evals() == 3 and r.get_json()["stale"] == 0
    # edit one label: evidence intact but the candidate is flagged stale
    crit[0]["label"] = "Management ≥ 7 ans"
    r = client.put(f"/api/jobs/{job['id']}/criteria", json=crit)
    assert [k["id"] for k in r.get_json()["criteria"]] == [k["id"] for k in job["criteria"]]
    assert n_evals() == 3 and r.get_json()["stale"] == 1
    # remove one criterion: only its evaluation disappears
    r = client.put(f"/api/jobs/{job['id']}/criteria", json=crit[:2])
    assert n_evals() == 2
    db.close()
