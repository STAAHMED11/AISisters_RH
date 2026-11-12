"""Flask application factory. The API lives under /api; the UI is the Next.js app (frontend/), which proxies /api here."""
import logging

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException as WerkzeugHTTPException

from . import auth
from .config import settings
from .db import init_db
from .routers import candidates, costs, jobs, outbox, public
from .web import HTTPException, close_db, run_background

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
try:  # persistent log file next to the database: easy to read when something goes wrong
    from logging.handlers import RotatingFileHandler
    _fh = RotatingFileHandler(settings.data_dir / "app.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger().addHandler(_fh)
except Exception:  # noqa: BLE001
    pass
log = logging.getLogger("app")


def _purge_unused_personal_data():
    """Data minimisation: the age is no longer extracted (never used); remove it from profiles stored before."""
    from .db import SessionLocal
    from .models import Candidate
    with SessionLocal() as s:
        changed = 0
        for c in s.query(Candidate).all():
            if c.profile and "age" in c.profile:
                c.profile = {k: v for k, v in c.profile.items() if k != "age"}
                changed += 1
        if changed:
            s.commit()
            log.info("removed the stored age from %s profile(s)", changed)


def _purge_orphan_costs():
    """Cost lines of offers that no longer exist (deleted before costs were removed with their offer)."""
    from sqlalchemy import delete, select

    from .db import SessionLocal
    from .models import Job, UsageEvent
    with SessionLocal() as s:
        n = s.execute(delete(UsageEvent).where(UsageEvent.job_id.is_not(None),
                                               UsageEvent.job_id.not_in(select(Job.id)))).rowcount
        s.commit()
        if n:
            log.info("removed %s cost line(s) of deleted offers", n)


def _startup():
    init_db()
    try:
        _purge_orphan_costs()
    except Exception:  # noqa: BLE001
        log.exception("orphan cost purge at startup failed")
    try:
        _purge_unused_personal_data()
    except Exception:  # noqa: BLE001
        log.exception("personal data purge at startup failed")
    try:  # thresholds may have changed since the candidates were screened (no LLM call involved)
        from .db import SessionLocal
        from .screening.retriage import retriage_all
        with SessionLocal() as s:
            retriage_all(s)
    except Exception:  # noqa: BLE001
        log.exception("retriage at startup failed")


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=testing, BACKGROUND_SYNC=testing, MAX_CONTENT_LENGTH=60 * 1024 * 1024)
    app.json.sort_keys = False
    app.json.ensure_ascii = False

    for bp in (auth.bp, jobs.bp, candidates.bp, public.bp, outbox.bp, costs.bp):
        app.register_blueprint(bp)

    # Teardown functions run in reverse order: background tasks are queued once the view has committed.
    app.teardown_request(run_background)
    app.teardown_appcontext(close_db)

    # A request that ends in an error must not leave work behind: background tasks it queued are dropped.
    @app.errorhandler(HTTPException)
    def _api_error(e: HTTPException):
        g.pop("bg_tasks", None)
        return jsonify({"detail": e.detail}), e.status_code

    @app.errorhandler(WerkzeugHTTPException)
    def _http_error(e: WerkzeugHTTPException):
        g.pop("bg_tasks", None)
        return jsonify({"detail": e.description}), e.code

    @app.errorhandler(Exception)
    def _unhandled(e: Exception):
        g.pop("bg_tasks", None)
        log.exception("Unhandled error on %s %s", request.method, request.path)
        return jsonify({"detail": f"Erreur serveur ({type(e).__name__}): {str(e)[:200]}"}), 500

    @app.get("/api/health")
    def health():
        from .screening.triage import MAYBE_AT, YES_AT
        return {
            "thresholds": {"yes": YES_AT, "maybe": MAYBE_AT},
            "ok": True,
            "anthropic": bool(settings.anthropic_api_key),
            "elevenlabs": bool(settings.elevenlabs_api_key and settings.elevenlabs_agent_id),
        }

    _startup()
    return app


app = create_app()  # gunicorn "backend.app.main:app"
