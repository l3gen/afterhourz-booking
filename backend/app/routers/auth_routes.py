from fastapi import APIRouter, Depends, HTTPException

from app import auth
from app.config import Settings, get_settings
from app.models import DevLogin, GoogleLogin

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _session(email: str, name: str, settings: Settings) -> dict:
    email = email.lower()
    return {
        "token": auth.issue_token(email, name, settings),
        "user": {"email": email, "name": name, "is_admin": email in settings.admin_email_set},
    }


@router.post("/google")
def google_login(body: GoogleLogin, settings: Settings = Depends(get_settings)):
    info = auth.verify_google_credential(body.credential, settings)
    return _session(info["email"], info.get("name", ""), settings)


@router.post("/dev-login")
def dev_login(body: DevLogin, settings: Settings = Depends(get_settings)):
    """Local development only. Config validation refuses DEV_LOGIN_ENABLED outside ENV=local."""
    if not (settings.env == "local" and settings.dev_login_enabled):
        raise HTTPException(404)
    return _session(body.email, body.name, settings)


@router.get("/me")
def me(user: auth.User = Depends(auth.current_user)):
    return {"email": user.email, "name": user.name, "is_admin": user.is_admin}
