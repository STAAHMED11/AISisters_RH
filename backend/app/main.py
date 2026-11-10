import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import auth
from .config import settings
from .db import get_db, init_db
from .models import AuditLog
from .routers import candidates, costs, jobs, outbox, public

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
try:  # persistent log file next to the database: easy to read when something goes wrong
    from logging.handlers import RotatingFileHandler
    _fh = RotatingFileHandler(settings.data_dir / "app.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger().addHandler(_fh)
except Exception:  # noqa: BLE001
    pass
log = logging.getLogger("app")

@asynccontextmanager
async def lifespan(_):
    init_db()
    try:  # thresholds may have changed since the candidates were screened (no LLM call involved)
        from .db import SessionLocal
        from .screening.retriage import retriage_all
        with SessionLocal() as db:
            retriage_all(db)
    except Exception:  # noqa: BLE001
        log.exception("retriage at startup failed")
    yield


app = FastAPI(title="RH du futur — Groupe Orvane", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": f"Erreur serveur ({type(exc).__name__}): {str(exc)[:200]}"}, status_code=500)


app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(public.router)
app.include_router(outbox.router)
app.include_router(costs.router)


@app.get("/api/health")
def health():
    from .screening.triage import MAYBE_AT, YES_AT
    return {
        "thresholds": {"yes": YES_AT, "maybe": MAYBE_AT},
        "ok": True,
        "anthropic": bool(settings.anthropic_api_key),
        "elevenlabs": bool(settings.elevenlabs_api_key and settings.elevenlabs_agent_id),
    }


# --- static frontend (built by Vite) with SPA fallback ---
dist = settings.frontend_dist
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = dist / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(dist / "index.html")
