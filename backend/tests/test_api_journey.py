"""The whole recruiter + candidate journey through the HTTP API, with the LLM stubbed (offline, free, deterministic)."""
import io
import re

import pytest

from backend.app import llm as llm_mod
from backend.app import schemas as S

CV = ("Karim BENALI\nResponsable d'entrepôt\nLyon · karim@mail.fr\n\n"
      "Direction d'un site de 35 000 m² approvisionnant 85 magasins, 45 collaborateurs. SAP EWM.\n").encode()


def _ids(text: str) -> list[int]:
    return [int(x) for x in re.findall(r"id=(\d+)", text)]


def fake_structured(tier, system, user, schema, **kw):
    if schema is S.CriteriaExtraction:
        return S.CriteriaExtraction(title="Responsable d'entrepôt", ref="R1", criteria=[
            S.CriterionIn(label="Management", description="≥ 5 ans, > 30 personnes", kind="must", source="cv"),
            S.CriterionIn(label="WMS", description="SAP EWM ou équivalent", kind="must", source="cv"),
            S.CriterionIn(label="Disponibilité", description="date de prise de poste", kind="nice", source="interview")])
    if schema is S.Profile:
        return S.Profile(is_cv=True, name="Karim Benali", email="karim@mail.fr", phone="", city="Lyon", age=38,
                         current_title="Responsable", years_experience=12, education_level="Bac+3", education=[],
                         languages=[], skills=[], certifications=[], cv_language="fr", headline="Responsable d'entrepôt")
    if schema is S.InjectionScan:
        return S.InjectionScan(injected=False, evidence=[])
    if schema is S.CVEvaluation:
        return S.CVEvaluation(summary="Profil solide", evaluations=[
            S.CritEval(criterion_id=i, verdict="met", quote="Direction d'un site de 35 000 m²", rationale="ok") for i in _ids(user)])
    if schema is S.InterviewPlan:
        return S.InterviewPlan(questions=[S.PlanQuestion(criterion_id=0, kind="closing", question="Des questions ?", listen_for="x")])
    if schema is S.Synthesis:
        return S.Synthesis(grades=[S.Grade(criterion_id=i, grade=3, quote="je dirige 45 personnes", rationale="ok") for i in _ids(user)],
                           strengths=[], doubts=[], probes=[], logistics=[], blockers=[], discrepancies=[],
                           recommendation="invite", headline="Solide", manipulation=False)
    if schema is S.Draft:
        return S.Draft(subject="Sujet", body="Bonjour")
    raise AssertionError(f"unexpected schema {schema}")


@pytest.fixture()
def stub_llm(monkeypatch):
    monkeypatch.setattr(llm_mod.llm, "structured", fake_structured)
    monkeypatch.setattr(llm_mod.llm, "chat", lambda *a, **k: "Merci, au revoir. [FIN]")


def _ok(r, *codes):
    codes = codes or (200,)
    assert r.status_code in codes, (r.status_code, r.get_data(as_text=True)[:300])
    body = r.get_data(as_text=True)
    assert not re.search(r'"\w{3}, \d\d \w{3} \d{4} \d\d:\d\d:\d\d GMT"', body), "dates must stay ISO 8601"
    return r.get_json(silent=True)



def test_journey(client, stub_llm):
    from backend.app.main import app
    job = _ok(client.post("/api/jobs", json={"description": "Responsable d'entrepôt logistique : 5 ans de management, SAP EWM, anglais."}))
    jid = job["id"]
    _ok(client.get("/api/jobs")); _ok(client.get(f"/api/jobs/{jid}")); _ok(client.get(f"/api/jobs/{jid}/overview"))
    crit = [{k: c[k] for k in ("id", "label", "description", "kind", "source")} for c in job["criteria"]]
    _ok(client.put(f"/api/jobs/{jid}/criteria", json=crit))

    up = _ok(client.post(f"/api/jobs/{jid}/candidates", data={"files": [(io.BytesIO(CV), "karim.txt")]},
                         content_type="multipart/form-data"))
    cid = up[0]["id"]
    d = _ok(client.get(f"/api/candidates/{cid}"))
    assert d["status"] == "screened" and d["triage"] == "yes"            # screened in the background
    assert d["interview"] and d["interview"]["plan_ready"]               # pre-qualified: interview prepared
    assert all(e["quote_verified"] for e in d["evaluations"])

    iv = _ok(client.post(f"/api/candidates/{cid}/invite"))
    token = iv["link"].rsplit("/", 1)[1]
    _ok(client.post(f"/api/candidates/{cid}/invite/send", json={}))       # SMTP blanked in tests: simulated

    with app.test_client() as cand:                                      # the candidate: no session cookie
        info = _ok(cand.get(f"/api/public/interview/{token}"))
        assert info["first_name"] == "Karim" and info["expired"] is False
        _ok(cand.post(f"/api/public/interview/{token}/message", json={"text": "x"}), 400, 409)   # consent first
        _ok(cand.post(f"/api/public/interview/{token}/consent", json={"language": "fr", "mode": "text"}))
        _ok(cand.post(f"/api/public/interview/{token}/start"))
        r = _ok(cand.post(f"/api/public/interview/{token}/message", json={"text": "Bonjour, je dirige 45 personnes depuis 7 ans."}))
        assert r["done"] is True
        _ok(cand.get(f"/api/public/interview/{token}/voice-session"), 409, 503)   # finished, or no ElevenLabs
        assert cand.get("/api/jobs").status_code == 401                 # the token gives no recruiter access

    d = _ok(client.get(f"/api/candidates/{cid}"))
    sc = d["interview"]["scores"]
    assert d["interview"]["status"] == "scored" and sc["note"] == 10.0 and sc["coverage"]["assessed"] == sc["coverage"]["total"]
    assert d["ai_proposal"] == "accept" and "cost" not in d

    _ok(client.post(f"/api/candidates/{cid}/decision", json={"decision": "accept", "comment": ""}))
    out = _ok(client.get(f"/api/jobs/{jid}/outbox"))
    drafts = [m for m in out["messages"] if m["status"] == "draft"]
    assert drafts, "a reply is drafted after the decision"
    _ok(client.put(f"/api/messages/{drafts[0]['id']}", json={"subject": "S", "body": "B"}))
    sent = _ok(client.post(f"/api/jobs/{jid}/outbox/send-all"))
    assert sent["failed"] == []
    assert _ok(client.get(f"/api/jobs/{jid}/outbox"))["stats"]["awaiting_reply"] == 0

    _ok(client.get("/api/mail-status")); _ok(client.post("/api/mail-test", json={"to": "a@b.fr"}))
    _ok(client.post(f"/api/candidates/{cid}/rescore")); _ok(client.post(f"/api/candidates/{cid}/reprocess"))
    _ok(client.post(f"/api/jobs/{jid}/rescreen")); _ok(client.post(f"/api/jobs/{jid}/reject-batch"))
    costs = _ok(client.get(f"/api/costs/jobs/{jid}"))
    assert "forecast" in costs and "by_purpose" in costs
    _ok(client.post(f"/api/jobs/{jid}/re-extract"))
    _ok(client.delete(f"/api/jobs/{jid}"))
    _ok(client.get(f"/api/jobs/{jid}"), 404)


def test_error_paths_return_readable_json(client):
    for method, url, kw, code in [
        ("post", "/api/candidates/999999/decision", {"json": {"decision": "accept"}}, 404),
        ("post", "/api/candidates/1/decision", {"json": {}}, 422),
        ("post", "/api/candidates/1/decision", {"data": "not json", "content_type": "text/plain"}, 422),
        ("post", "/api/jobs/1/candidates", {}, 422),
        ("get", "/api/nope", {}, 404),
        ("delete", "/api/health", {}, 405),
        ("get", "/api/public/interview/short", {}, 404),
    ]:
        r = getattr(client, method)(url, **kw)
        assert r.status_code == code, (url, r.status_code)
        assert isinstance((r.get_json() or {}).get("detail"), str), url
