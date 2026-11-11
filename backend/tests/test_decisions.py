from backend.app import llm as llm_mod
from backend.app.db import SessionLocal
from backend.app.models import Candidate, Criterion, Job
from backend.app.schemas import Draft


def _actions():
    from sqlalchemy import select

    from backend.app.db import SessionLocal
    from backend.app.models import AuditLog
    with SessionLocal() as db:
        return [a for a in db.scalars(select(AuditLog.action)).all()]

def _candidate(triage: str) -> int:
    db = SessionLocal()
    job = Job(title="Poste", description="x" * 50)
    job.criteria.append(Criterion(label="Mgmt", kind="must", source="cv"))
    db.add(job); db.flush()
    c = Candidate(job_id=job.id, filename="x.pdf", status="screened", triage=triage, profile={"name": "Jean Test", "email": "j@t.fr"})
    db.add(c); db.commit()
    cid = c.id
    db.close()
    return cid


def test_override_needs_comment_and_is_audited(client, monkeypatch):
    monkeypatch.setattr(llm_mod.llm, "structured", lambda *a, **k: Draft(subject="Sujet", body="Corps du message"))
    cid = _candidate("no")  # AI proposes: reject
    assert client.get(f"/api/candidates/{cid}").get_json()["ai_proposal"] == "reject"
    r = client.post(f"/api/candidates/{cid}/decision", json={"decision": "accept", "comment": ""})
    assert r.status_code == 400  # contradicting the AI without a comment is refused
    r = client.post(f"/api/candidates/{cid}/decision", json={"decision": "accept", "comment": "Profil atypique à voir"})
    assert r.status_code == 200 and r.get_json()["override"] is True
    d = client.get(f"/api/candidates/{cid}").get_json()
    assert d["decision"] == "accepted" and d["decisions"][-1]["override"] is True
    actions = _actions()
    assert "decision_override" in actions


def test_agreeing_with_ai_needs_no_comment_and_drafts_reply(client, monkeypatch):
    monkeypatch.setattr(llm_mod.llm, "structured", lambda *a, **k: Draft(subject="Sujet", body="Corps du message"))
    cid = _candidate("no")
    r = client.post(f"/api/candidates/{cid}/decision", json={"decision": "reject", "comment": ""})
    assert r.status_code == 200 and r.get_json()["override"] is False
    d = client.get(f"/api/candidates/{cid}").get_json()
    assert [m["kind"] for m in d["messages"]] == ["rejection"]  # reply drafted, not sent
    assert d["messages"][0]["status"] == "draft"
    job_id = d["job"]["id"]
    out = client.get(f"/api/jobs/{job_id}/outbox").get_json()
    assert out["stats"]["awaiting_reply"] == 1
    client.post(f"/api/messages/{out['messages'][0]['id']}/send")
    assert client.get(f"/api/jobs/{job_id}/outbox").get_json()["stats"] == {
        "candidates": 1, "decided": 1, "awaiting_reply": 0, "replied": 1, "rejections_to_validate": 0}


def test_retriage_applies_new_threshold_without_llm(client):
    from backend.app.models import Evaluation
    from backend.app.screening.retriage import retriage_all
    db = SessionLocal()
    job = Job(title="Poste", description="x" * 50)
    for i in range(7):
        job.criteria.append(Criterion(label=f"c{i}", kind="must" if i < 6 else "nice", source="cv"))
    db.add(job); db.flush()
    c = Candidate(job_id=job.id, filename="x.pdf", status="screened", triage="maybe", prequal="review", cv_score=0.73)
    db.add(c); db.flush()
    verdicts = ["met"] * 3 + ["partial"] * 2 + ["not_evidenced", "met"]  # score 0.73
    for k, v in zip(job.criteria, verdicts):
        db.add(Evaluation(candidate_id=c.id, criterion_id=k.id, verdict=v, quote="q" * 10, quote_verified=True))
    db.commit()
    assert retriage_all(db) >= 1
    db.refresh(c)
    assert (c.triage, c.prequal) == ("yes", "pass")  # stored as 'maybe' under the old 75% rule, 'yes' under 70%
    db.close()


def test_job_overview_builds_funnel_and_todo(client):
    from backend.app.models import Interview, Message, now
    db = SessionLocal()
    job = Job(title="Offre", description="x" * 50)
    job.criteria.append(Criterion(label="m", kind="must", source="cv"))
    db.add(job); db.flush()

    def cand(**kw):
        c = Candidate(job_id=job.id, filename="x.pdf", profile={"name": "N"}, **kw)
        db.add(c); db.flush(); return c
    scored = cand(status="screened", triage="yes")                                # interview done -> to decide
    db.add(Interview(candidate_id=scored.id, plan={}, status="scored"))
    unsent = cand(status="screened", triage="yes")                                # link ready, invitation not sent
    db.add(Interview(candidate_id=unsent.id, plan={}, status="pending"))
    db.add(Message(candidate_id=unsent.id, kind="invite", status="draft"))
    waiting = cand(status="screened", triage="yes")                               # invitation sent, candidate hasn't answered
    db.add(Interview(candidate_id=waiting.id, plan={}, status="pending"))
    db.add(Message(candidate_id=waiting.id, kind="invite", status="sent", sent_at=now()))
    cand(status="screened", triage="maybe")                                        # to review
    cand(status="screened", triage="no")                                           # rejection to validate
    cand(status="failed")
    cand(status="screening")
    db.commit(); jid = job.id; db.close()

    o = client.get(f"/api/jobs/{jid}/overview").get_json()
    todo = {t["key"]: t["count"] for t in o["todo"]}
    assert todo == {"to_decide": 1, "to_review": 1, "invites_unsent": 1, "rejections": 1, "failed": 1, "busy": 1, "waiting": 1}
    assert o["funnel"]["received"] == 7 and o["funnel"]["analyzed"] == 5 and o["funnel"]["prequalified"] == 3 and o["funnel"]["interviewed"] == 1
    assert o["todo_count"] == 5   # "busy" and "waiting" are informational, not tasks
    assert [t["key"] for t in o["todo"]][0] == "to_decide"   # decisions come first
    assert client.get("/api/jobs").get_json()[0]["todo_count"] >= 0
