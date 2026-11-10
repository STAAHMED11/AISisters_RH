def test_health_login_audit(client):
    assert client.get("/api/health").json()["ok"]
    assert client.get("/api/me").status_code == 200


def test_requires_auth():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as c:
        assert c.get("/api/jobs").status_code == 401
        assert c.post("/api/login", json={"password": "bad"}).status_code == 401
