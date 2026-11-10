import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["APP_PASSWORD"] = "pw"

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        c.post("/api/login", json={"password": "pw", "name": "Sylvie"})
        yield c
