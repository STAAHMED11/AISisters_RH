import hmac

from fastapi import APIRouter, Cookie, HTTPException, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel

from .config import settings

router = APIRouter(prefix="/api", tags=["auth"])
_ser = URLSafeTimedSerializer(settings.secret_key, salt="recruiter")
COOKIE = "orvane_session"
MAX_AGE = 60 * 60 * 24 * 7


class LoginIn(BaseModel):
    password: str
    name: str = "Recruteur"


def current_user(orvane_session: str | None = Cookie(default=None)) -> str:
    if not orvane_session:
        raise HTTPException(401, "Non connecté")
    try:
        data = _ser.loads(orvane_session, max_age=MAX_AGE)
    except BadSignature:
        raise HTTPException(401, "Session invalide")
    return data["name"]


@router.post("/login")
def login(body: LoginIn, response: Response):
    if not hmac.compare_digest(body.password.encode(), settings.app_password.encode()):
        raise HTTPException(401, "Mot de passe incorrect")
    name = (body.name or "Recruteur").strip()[:60] or "Recruteur"
    response.set_cookie(
        COOKIE, _ser.dumps({"name": name}), max_age=MAX_AGE, httponly=True, samesite="lax",
        secure=settings.public_url.startswith("https://"),
    )
    return {"name": name}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}


@router.get("/me")
def me(orvane_session: str | None = Cookie(default=None)):
    return {"name": current_user(orvane_session)}
