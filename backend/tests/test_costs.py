from types import SimpleNamespace as U

from backend.app import costs
from backend.app.db import SessionLocal
from backend.app.models import Candidate, Job, UsageEvent


def test_llm_cost_math_matches_list_prices():
    # Sonnet 5.5: $2 / $10 per MTok ; Haiku 5.5: $0.10 / $0.50 per MTok
    c, exact = costs.llm_cost("claude-sonnet-5-5", 10_000, 2_000)
    assert exact and abs(c - (10_000 * 2 + 2_000 * 10) / 1e6) < 1e-12 and round(c, 4) == 0.04
    c, _ = costs.llm_cost("claude-haiku-5-5", 10_000, 1_000)
    assert round(c, 6) == round((10_000 * 0.10 + 1_000 * 0.50) / 1e6, 6)
    c, _ = costs.llm_cost("claude-haiku-5-5", 200_000, 0)  # long-prompt tier
    assert round(c, 4) == round(200_000 * 0.50 / 1e6, 4)
    c, exact = costs.llm_cost("some-future-model", 1_000_000, 0)
    assert exact is False and c == 2.0  # unknown model: fallback price, flagged as estimated


def test_purposes_map_to_groups():
    assert costs.group_of("evaluate") == "cv" and costs.group_of("score") == "interview"
    assert costs.group_of("voice_call") == "voice" and costs.group_of("draft_rejection") == "other"


def _seed():
    db = SessionLocal()
    job = Job(title="Offre coûts", description="x" * 50)
    db.add(job); db.flush()
    cands = []
    for i in range(2):
        c = Candidate(job_id=job.id, filename=f"{i}.pdf", status="screened", triage="yes" if i == 0 else "no", profile={"name": f"Cand {i}"})
        db.add(c); db.flush(); cands.append(c)
    jid, ids = job.id, [c.id for c in cands]
    db.commit(); db.close()
    return jid, ids


def test_job_cost_aggregation_per_cv_and_per_interview(client, monkeypatch):
    jid, (a, b) = _seed()
    rec = costs.record
    for cand in (a, b):  # 2 CV analysed: 0.01 + 0.02 each
        rec("anthropic", "profile", model="claude-haiku-5-5", job_id=jid, candidate_id=cand, cost_usd=0.01, input_tokens=100, output_tokens=50)
        rec("anthropic", "evaluate", model="claude-sonnet-5-5", job_id=jid, candidate_id=cand, cost_usd=0.02, input_tokens=900, output_tokens=300)
    rec("anthropic", "plan", model="claude-sonnet-5-5", job_id=jid, candidate_id=a, cost_usd=0.03)         # 1 interview
    rec("elevenlabs", "voice_call", model="elevenlabs-agent", job_id=jid, candidate_id=a, cost_usd=0.05, ref="conv1", meta={"duration_secs": 60})
    rec("anthropic", "draft_rejection", model="claude-haiku-5-5", job_id=jid, candidate_id=b, cost_usd=0.004)
    rec("anthropic", "criteria", model="claude-sonnet-5-5", job_id=jid, cost_usd=0.006)
    d = client.get(f"/api/costs/jobs/{jid}").json()
    assert d["cost"]["cv"] == 0.06 and d["cost"]["interview"] == 0.03 and d["cost"]["voice"] == 0.05
    assert round(d["cost"]["other"], 6) == 0.01 and round(d["cost"]["total"], 6) == 0.15
    assert d["cv_analyzed"] == 2 and d["per_cv"] == 0.03          # 0.06 / 2 CV
    assert d["interviews"] == 1 and d["per_interview"] == 0.08    # (0.03 + 0.05) / 1 interview
    assert d["voice_minutes"] == 1.0
    assert d["candidates"][0]["id"] == a and d["forecast"]["yes_rate"] == 0.5 and d["forecast"]["avg_reply"] == 0.004
    ov = client.get("/api/costs").json()
    row = next(r for r in ov["jobs"] if r["id"] == jid)
    assert row["cost"]["total"] == 0.15 and ov["total"] >= 0.15
    assert client.get(f"/api/candidates/{a}").json()["cost"]["total"] == 0.11  # 0.01+0.02+0.03+0.05
    assert client.get(f"/api/jobs/{jid}").json()["cost_total"] == 0.15


def test_voice_cost_uses_elevenlabs_cost_fiat_and_is_not_double_counted():
    jid, (a, _) = _seed()
    conv = {"conversation_id": "conv_x", "metadata": {"call_duration_secs": 36, "cost": 270, "cost_fiat": 0.0491,
                                                      "charging": {"llm_price": 0.0007, "platform_price": 0.0484}}}
    costs.record_voice(conv, jid, a)
    costs.record_voice(conv, jid, a)  # re-fetching the same call must not bill twice
    db = SessionLocal()
    rows = db.query(UsageEvent).filter_by(provider="elevenlabs", ref="conv_x").all()
    assert len(rows) == 1 and rows[0].cost_usd == 0.0491 and rows[0].meta["duration_secs"] == 36
    # no cost_fiat reported: estimate from the duration at $0.08/min and flag it
    costs.record_voice({"conversation_id": "conv_y", "metadata": {"call_duration_secs": 90}}, jid, a)
    est = db.query(UsageEvent).filter_by(ref="conv_y").one()
    assert round(est.cost_usd, 4) == 0.12 and est.meta["estimated"] is True
    db.close()


def test_record_llm_ignores_calls_without_context_and_never_raises():
    n = SessionLocal().query(UsageEvent).count()
    costs.record_llm("claude-haiku-5-5", U(input_tokens=5, output_tokens=5), None)   # no context -> nothing recorded
    assert SessionLocal().query(UsageEvent).count() == n
    costs.record_llm("claude-haiku-5-5", U(input_tokens=5, output_tokens=5), {"purpose": "profile", "job_id": 1, "candidate_id": 1})
    assert SessionLocal().query(UsageEvent).count() == n + 1


def test_candidate_history_replaces_the_audit_page(client):
    from backend.app.audit import log_event
    jid, (a, b) = _seed()
    db = SessionLocal()
    log_event(db, "IA", "cv_screened", "candidate", a, triage="yes", score=0.9)
    log_event(db, "Sylvie", "decision_override", "candidate", a, decision="accept", comment="atypique")
    log_event(db, "candidat", "interview_ended", "candidate", a, mode="voice")
    log_event(db, "IA", "cv_screened", "candidate", b, triage="no", score=0.1)   # another candidate: must not leak
    db.close()
    h = client.get(f"/api/candidates/{a}").json()["history"]
    assert [e["action"] for e in h] == ["interview_ended", "decision_override", "cv_screened"]   # newest first
    assert [e["actor_type"] for e in h] == ["candidate", "recruiter", "ia"]
    assert client.get("/api/audit").status_code in (404, 405)   # the standalone page and its endpoint are gone
