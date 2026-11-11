"""Small Flask toolkit shared by every blueprint.

- `HTTPException(status, detail)`: raise it anywhere in a view -> JSON `{"detail": ...}` with that status.
- `db()`: the SQLAlchemy session of the current request (opened lazily, closed at teardown).
- `@login_required`: recruiter routes; the recruiter's name is passed to the view as `user`.
- `parse(Model)`: validate the JSON body with Pydantic (422 with readable errors otherwise).
- `background(fn, *args)`: run `fn` AFTER the response, in a dedicated thread pool (never the request threads).
  Tasks are queued during the request and submitted at teardown, i.e. once the view has committed.
"""
import functools
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

from flask import current_app, g, request
from pydantic import BaseModel, TypeAdapter, ValidationError

from .db import SessionLocal

log = logging.getLogger("web")
T = TypeVar("T")

# Dedicated pool: long AI jobs (CV screening, interview scoring, ElevenLabs polling) never starve the HTTP threads.
_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="bg")


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str = ""):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


def db():
    if "db" not in g:
        g.db = SessionLocal()
    return g.db


def close_db(_exc=None):
    s = g.pop("db", None)
    if s is not None:
        s.close()


def parse(model: type[T] | object, *, default=None) -> T:
    """Validate the request JSON against a Pydantic model (or any type, e.g. list[Model])."""
    data = request.get_json(silent=True)
    if data is None:
        data = default if default is not None else {}
    try:
        if isinstance(model, type) and issubclass(model, BaseModel):
            return model.model_validate(data)
        return TypeAdapter(model).validate_python(data)
    except ValidationError as e:
        raise HTTPException(422, "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())) from None


def login_required(view):
    from .auth import current_user

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        kwargs["user"] = current_user()
        return view(*args, **kwargs)
    return wrapper


def background(fn, *args, **kwargs):
    g.setdefault("bg_tasks", []).append((fn, args, kwargs))


def _safe(fn, args, kwargs):
    try:
        fn(*args, **kwargs)
    except Exception:  # noqa: BLE001
        log.exception("background task %s failed", getattr(fn, "__name__", fn))


def run_background(_exc=None):
    tasks = g.pop("bg_tasks", [])
    for fn, args, kwargs in tasks:
        if current_app.config.get("BACKGROUND_SYNC"):  # tests: deterministic, like Starlette's TestClient
            _safe(fn, args, kwargs)
        else:
            _pool.submit(_safe, fn, args, kwargs)
