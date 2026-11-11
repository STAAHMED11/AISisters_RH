import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["APP_PASSWORD"] = "pw"

import pytest

from backend.app.main import app

app.config.update(TESTING=True, BACKGROUND_SYNC=True)  # background tasks run inline: deterministic tests


@pytest.fixture()
def client():
    with app.test_client() as c:
        c.post("/api/login", json={"password": "pw", "name": "Sylvie"})
        yield c
