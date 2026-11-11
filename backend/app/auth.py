import hmac

from flask import Blueprint, jsonify, request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel

from .config import settings
from .web import HTTPException, parse

bp = Blueprint("auth", __name__, url_prefix="/api")
_ser = URLSafeTimedSerializer(settings.secret_key, salt="recruiter")
COOKIE = "orvane_session"
MAX_AGE = 60 * 60 * 24 * 7


class LoginIn(BaseModel):
    password: str
    name: str = "Recruteur"


def current_user() -> str:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Non connecté")
    try:
        data = _ser.loads(token, max_age=MAX_AGE)
    except BadSignature:
        raise HTTPException(401, "Session invalide") from None
    return data["name"]


@bp.post("/login")
def login():
    body = parse(LoginIn)
    if not hmac.compare_digest(body.password.encode(), settings.app_password.encode()):
        raise HTTPException(401, "Mot de passe incorrect")
    name = (body.name or "Recruteur").strip()[:60] or "Recruteur"
    resp = jsonify({"name": name})
    resp.set_cookie(
        COOKIE, _ser.dumps({"name": name}), max_age=MAX_AGE, httponly=True, samesite="Lax",
        secure=settings.public_url.startswith("https://"),
    )
    return resp


@bp.post("/logout")
def logout():
    resp = jsonify({"ok": True})
    resp.delete_cookie(COOKIE)
    return resp


@bp.get("/me")
def me():
    return {"name": current_user()}
