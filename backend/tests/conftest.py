import os
import tempfile

# Tests are hermetic: never the developer's real database, API keys or mail server, whatever is in .env.
# (Set before the app is imported; python-dotenv never overrides variables that already exist.)
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["APP_PASSWORD"] = "pw"
for var in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_ID",
            "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"):
    os.environ[var] = ""          # no paid AI call, no real e-mail: tests that need them stub them
os.environ["AUTO_SEND_INVITES"] = "0"

import pytest

from backend.app.main import app

app.config.update(TESTING=True, BACKGROUND_SYNC=True)  # background tasks run inline: deterministic tests


@pytest.fixture()
def client():
    with app.test_client() as c:
        c.post("/api/login", json={"password": "pw", "name": "Sylvie"})
        yield c
