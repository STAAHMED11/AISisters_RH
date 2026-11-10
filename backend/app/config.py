import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


class Settings:
    anthropic_api_key = _env("ANTHROPIC_API_KEY")
    model_smart = _env("MODEL_SMART", "claude-sonnet-5-5")
    model_fast = _env("MODEL_FAST", "claude-haiku-5-5")
    llm_timeout = float(_env("LLM_TIMEOUT", "90"))

    elevenlabs_api_key = _env("ELEVENLABS_API_KEY")
    elevenlabs_agent_id = _env("ELEVENLABS_AGENT_ID")
    elevenlabs_webhook_secret = _env("ELEVENLABS_WEBHOOK_SECRET")

    app_password = _env("APP_PASSWORD", "orvane")
    secret_key = _env("SECRET_KEY", "dev-secret-change-me")
    public_url = _env("PUBLIC_URL", "http://localhost:8000").rstrip("/")

    yes_threshold = float(_env("YES_THRESHOLD", "0.70"))     # CV score needed to pass to the pre-interview
    maybe_threshold = float(_env("MAYBE_THRESHOLD", "0.45"))  # below this: refusal proposed (recruiter validates)
    auto_send_invites = _env("AUTO_SEND_INVITES", "0") == "1"  # e-mail the pre-interview link to pre-qualified (Yes) candidates without a click
    interview_valid_days = int(_env("INTERVIEW_VALID_DAYS", "7"))
    smtp_host = _env("SMTP_HOST")
    smtp_port = int(_env("SMTP_PORT", "587"))
    smtp_user = _env("SMTP_USER")
    smtp_password = _env("SMTP_PASSWORD")
    smtp_from = _env("SMTP_FROM")  # e.g. "Recrutement Orvane <recrutement@orvane.fr>"
    smtp_tls = _env("SMTP_TLS", "1") != "0"  # STARTTLS on 587 (port 465 uses SSL automatically)

    db_journal = _env("DB_JOURNAL", "WAL").upper()
    data_dir = Path(_env("DATA_DIR", str(ROOT / "data")))
    frontend_dist = ROOT / "frontend" / "dist"

    @property
    def database_url(self) -> str:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return _env("DATABASE_URL", f"sqlite:///{self.data_dir / 'app.db'}")


settings = Settings()
