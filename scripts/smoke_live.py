"""Read-only checks of the deployed app: health, pages, login, API. Sends no e-mail and makes no LLM call.

    python scripts/smoke_live.py [URL]        (default: PUBLIC_URL from .env; password: APP_PASSWORD)
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.config import settings  # noqa: E402


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else settings.public_url).rstrip("/")
    failures = []

    def check(label, ok, detail=""):
        print(f"{'✅' if ok else '❌'} {label}{(' — ' + detail) if detail and not ok else ''}")
        if not ok:
            failures.append(label)

    with httpx.Client(base_url=base, timeout=30, follow_redirects=True) as c:
        h = c.get("/api/health")
        check("health", h.status_code == 200 and h.json().get("ok"), h.text[:120])
        check("AI and voice configured", h.status_code == 200 and h.json().get("anthropic") and h.json().get("elevenlabs"))
        for page in ("/jobs", "/i/not-a-real-token-but-long-enough"):
            r = c.get(page)
            check(f"page {page}", r.status_code == 200 and "<html" in r.text.lower(), str(r.status_code))
        check("recruiter API protected", c.get("/api/jobs").status_code == 401)
        check("unknown interview link refused", c.get("/api/public/interview/not-a-real-token-but-long-enough").status_code == 404)
        login = c.post("/api/login", json={"password": settings.app_password, "name": "smoke-test"})
        check("login", login.status_code == 200, login.text[:120])
        if login.status_code == 200:
            jobs = c.get("/api/jobs")
            check("offers list", jobs.status_code == 200 and isinstance(jobs.json(), list))
            mail = c.get("/api/mail-status")
            check("e-mail configured (SMTP)", mail.status_code == 200 and mail.json().get("smtp"), mail.text[:120])
            c.post("/api/logout")
    print(f"\n{base}: {'OK' if not failures else str(len(failures)) + ' check(s) failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
