import secrets
from datetime import timedelta

from backend.app import llm as llm_mod
from backend.app import mailer
from backend.app.config import settings
from backend.app.db import SessionLocal
from backend.app.models import Candidate, Criterion, Interview, Job, now
from backend.app.schemas import Draft


def _candidate(expires_in_days: float = 7, status: str = "pending") -> tuple[int, str]:
    db = SessionLocal()
    job = Job(title="Responsable d'entrepôt", description="x" * 50)
    job.criteria.append(Criterion(label="Mgmt", kind="must", source="cv"))
    db.add(job); db.flush()
    c = Candidate(job_id=job.id, filename="a.pdf", status="screened", triage="yes", token="tok_" + secrets.token_hex(16),
                  profile={"name": "Karim Benali", "email": "karim@example.fr"})
    db.add(c); db.flush()
    db.add(Interview(candidate_id=c.id, plan={"questions": []}, language="fr", status=status,
                     expires_at=now() + timedelta(days=expires_in_days)))
    db.commit()
    out = (c.id, c.token)
    db.close()
    return out


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout=0, **kw):
        self.host, self.port = host, port

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self, **kw): pass
    def login(self, u, p): pass
    def send_message(self, msg): FakeSMTP.sent.append(msg)


def test_invitation_email_has_link_and_deadline(client, monkeypatch):
    monkeypatch.setattr(llm_mod.llm, "structured", lambda *a, **k: Draft(subject="Votre pré-entretien", body="Bonjour Karim, voici votre invitation."))
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_from", "recrutement@orvane.test")
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent.clear()
    cid, token = _candidate()
    d = client.post(f"/api/candidates/{cid}/invite/send", json={}).get_json()
    assert d["invite"]["state"] == "sent" and d["invite"]["transport"] == "smtp" and d["invite"]["to"] == "karim@example.fr"
    msg = FakeSMTP.sent[-1]
    body = msg.get_body(preferencelist=("plain",)).get_content()   # plain-text part (always sent as fallback)
    assert msg["To"] == "karim@example.fr" and f"/i/{token}" in body            # link guaranteed in the e-mail
    assert d["expires_label"] in body and "valable jusqu" in body              # deadline guaranteed in the e-mail
    html = msg.get_body(preferencelist=("html",)).get_content()                # HTML version with a real button
    assert msg.is_multipart() and f'href="http' in html and f"/i/{token}" in html and "Passer le pré-entretien" in html and d["expires_label"] in html
    # sending again without extend does not email twice
    n = len(FakeSMTP.sent)
    client.post(f"/api/candidates/{cid}/invite/send", json={})
    assert len(FakeSMTP.sent) == n
    # extend renews the deadline and sends a fresh e-mail
    client.post(f"/api/candidates/{cid}/invite/send", json={"extend": True})
    assert len(FakeSMTP.sent) == n + 1


def test_mock_when_smtp_not_configured(client, monkeypatch):
    monkeypatch.setattr(llm_mod.llm, "structured", lambda *a, **k: Draft(subject="S", body="B"))
    monkeypatch.setattr(settings, "smtp_host", "")
    cid, _ = _candidate()
    d = client.post(f"/api/candidates/{cid}/invite/send", json={}).get_json()
    assert d["invite"]["transport"] == "mock" and d["invite"]["smtp"] is False


def test_candidate_without_email_cannot_be_sent(client, monkeypatch):
    monkeypatch.setattr(llm_mod.llm, "structured", lambda *a, **k: Draft(subject="S", body="B"))
    cid, _ = _candidate()
    db = SessionLocal(); c = db.get(Candidate, cid); c.profile = {"name": "X"}; db.commit(); db.close()
    r = client.post(f"/api/candidates/{cid}/invite/send", json={})
    assert r.status_code == 502 and "e-mail" in r.get_json()["detail"]


def test_expired_link_is_refused_but_finished_interviews_stay_readable(client):
    from backend.app.main import app
    cid, token = _candidate(expires_in_days=-1)                       # deadline passed yesterday
    with app.test_client() as anon:                                      # candidate: no session cookie
        info = anon.get(f"/api/public/interview/{token}").get_json()
        assert info["expired"] is True
        assert anon.post(f"/api/public/interview/{token}/consent", json={"language": "fr", "mode": "text"}).status_code == 410
        assert anon.post(f"/api/public/interview/{token}/start").status_code in (400, 410)
    cid2, token2 = _candidate(expires_in_days=3)
    with app.test_client() as anon:
        assert anon.get(f"/api/public/interview/{token2}").get_json()["expired"] is False
        assert anon.post(f"/api/public/interview/{token2}/consent", json={"language": "fr", "mode": "text"}).status_code == 200
    cid3, token3 = _candidate(expires_in_days=-1, status="scored")      # already done: not "expired"
    with app.test_client() as anon:
        assert anon.get(f"/api/public/interview/{token3}").get_json()["expired"] is False


def test_mail_test_endpoint_reports_the_transport(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent.clear()
    r = client.post("/api/mail-test", json={"to": "recruteur@example.fr"})
    assert r.status_code == 200 and r.get_json()["transport"] == "smtp"
    assert FakeSMTP.sent[-1]["To"] == "recruteur@example.fr" and FakeSMTP.sent[-1].is_multipart()
    assert client.post("/api/mail-test", json={"to": "pas-un-email"}).status_code == 502
    monkeypatch.setattr(settings, "smtp_host", "")
    assert client.post("/api/mail-test", json={"to": "recruteur@example.fr"}).get_json()["transport"] == "mock"
    st = client.get("/api/mail-status").get_json()
    assert st["smtp"] is False and "password" not in str(st).lower()


def test_auto_send_invites_sends_the_draft_to_a_prequalified_candidate(client, monkeypatch):
    from backend.app.comms import send_pending_invite
    from backend.app.models import Message
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent.clear()
    cid, token = _candidate()
    db = SessionLocal()
    db.add(Message(candidate_id=cid, kind="invite", language="fr", subject="Invitation", body="Bonjour,\n\nVoici votre invitation.", status="draft"))
    db.commit()
    c = db.get(Candidate, cid)
    assert send_pending_invite(db, c) is True and len(FakeSMTP.sent) == 1
    assert send_pending_invite(db, c) is False and len(FakeSMTP.sent) == 1   # nothing left to send: never e-mails twice
    db.close()


# ---------------------------------------------------------------- instant link + race safety
def _fresh_candidate(with_email: str = "karim@example.fr") -> int:
    db = SessionLocal()
    job = Job(title="Responsable d'entrepôt", description="x" * 50)
    job.criteria.append(Criterion(label="Mgmt", kind="must", source="cv"))
    db.add(job); db.flush()
    c = Candidate(job_id=job.id, filename="a.pdf", status="screened", triage="yes", profile={"name": "Karim Benali", "email": with_email})
    db.add(c); db.commit()
    cid = c.id
    db.close()
    return cid


def _stub_llm(monkeypatch, counter: dict | None = None):
    import time
    from backend.app.schemas import InterviewPlan, PlanQuestion

    def fake(tier, system, user, schema, **kw):
        if counter is not None:
            counter[schema.__name__] = counter.get(schema.__name__, 0) + 1
        time.sleep(0.15)  # a real AI call is slow: this is what opens the race window
        if schema is InterviewPlan:
            return InterviewPlan(questions=[PlanQuestion(criterion_id=0, kind="closing", question="Une question ?", listen_for="x")])
        return Draft(subject="Invitation", body="Bonjour, voici votre invitation.")
    monkeypatch.setattr(llm_mod.llm, "structured", fake)


def test_creating_the_interview_is_instant_and_safe_under_concurrent_clicks(monkeypatch):
    """Regression: 'UNIQUE constraint failed: interviews.candidate_id' when the background preparation and a click collided."""
    import threading
    from backend.app.interview.service import create_interview
    monkeypatch.setattr(llm_mod.llm, "structured", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no AI call allowed")))  # instant = no LLM
    cid = _fresh_candidate()
    tokens, errors = [], []

    def worker():
        try:
            with SessionLocal() as db:
                tokens.append(create_interview(db, db.get(Candidate, cid)).candidate.token)
        except Exception as e:  # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errors and len(set(tokens)) == 1 and tokens[0]
    with SessionLocal() as db:
        assert db.query(Interview).filter_by(candidate_id=cid).count() == 1


def test_plan_and_invite_draft_are_built_only_once(monkeypatch):
    import threading
    from backend.app.interview.service import create_interview, prepare_assets
    from backend.app.models import Message
    calls: dict = {}
    _stub_llm(monkeypatch, calls)
    cid = _fresh_candidate()
    with SessionLocal() as db:
        create_interview(db, db.get(Candidate, cid))
    errors = []

    def worker():
        try:
            with SessionLocal() as db:
                prepare_assets(db, db.get(Candidate, cid))
        except Exception as e:  # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=worker) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errors
    assert calls.get("InterviewPlan") == 1 and calls.get("Draft") == 1      # one AI call each, not six
    with SessionLocal() as db:
        assert db.query(Message).filter_by(candidate_id=cid, kind="invite").count() == 1
        assert db.get(Candidate, cid).interview.plan["questions"]


def test_clicking_invite_while_the_pipeline_prepares_the_interview_does_not_crash(client, monkeypatch):
    import threading
    from backend.app.interview.service import ensure_interview
    _stub_llm(monkeypatch)
    cid = _fresh_candidate()
    errors = []

    def pipeline():   # what the screening does for a pre-qualified candidate
        try:
            with SessionLocal() as db:
                ensure_interview(db, db.get(Candidate, cid))
        except Exception as e:  # noqa: BLE001
            errors.append(e)
    t = threading.Thread(target=pipeline); t.start()
    r = client.post(f"/api/candidates/{cid}/invite")          # the recruiter clicks at the same moment
    t.join()
    assert r.status_code == 200 and r.get_json()["link"].endswith(r.get_json()["link"].rsplit("/", 1)[1]) and not errors
    d = client.get(f"/api/candidates/{cid}").get_json()["interview"]
    assert d["plan_ready"] is True and d["status"] == "pending"
    assert client.post(f"/api/candidates/{cid}/invite").status_code == 200   # idempotent
