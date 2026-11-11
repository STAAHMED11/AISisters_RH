def test_health_login_audit(client):
    assert client.get("/api/health").get_json()["ok"]
    assert client.get("/api/me").status_code == 200


def test_requires_auth():
    from backend.app.main import app
    with app.test_client() as c:
        assert c.get("/api/jobs").status_code == 401
        assert c.post("/api/login", json={"password": "bad"}).status_code == 401


def test_background_work_is_dropped_when_the_request_fails():
    """Same rule as before the Flask migration: a request that ends in an error leaves no background task behind."""
    from backend.app.main import create_app
    from backend.app.web import HTTPException, background
    app2 = create_app(testing=True)
    ran = []

    @app2.post("/api/_probe/<int:fail>")
    def _probe(fail: int):
        background(ran.append, fail)
        if fail:
            raise HTTPException(409, "refused")
        return {"ok": True}

    with app2.test_client() as c:
        assert c.post("/api/_probe/1").status_code == 409
        assert c.post("/api/_probe/0").status_code == 200
    assert ran == [0]
