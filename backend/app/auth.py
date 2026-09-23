"""Google sign-in -> our own short-lived session JWT.

The browser gets a Google ID token from Google Identity Services, sends it to
POST /api/auth/google, and we verify it (signature, audience, expiry) before minting
our own JWT. Admins are simply Google accounts listed in ADMIN_EMAILS; there are no
passwords to store or leak.
"""

import datetime as dt

import jwt
from fastapi import Depends, HTTPException, Request
from google.auth.transport import requests as g_requests
from google.oauth2 import id_token

from app.config import Settings, get_settings
from app.timeutil import now_utc


def verify_google_credential(credential: str, settings: Settings) -> dict:
    """Returns the verified Google claims. Monkeypatched in tests."""
    if not settings.google_client_id:
        raise HTTPException(503, "Google sign-in is not configured")
    try:
        info = id_token.verify_oauth2_token(credential, g_requests.Request(), settings.google_client_id)
    except ValueError as e:
        raise HTTPException(401, "Invalid Google credential") from e
    if not info.get("email_verified"):
        raise HTTPException(401, "Google account email is not verified")
    return info


def issue_token(email: str, name: str, settings: Settings) -> str:
    now = now_utc()
    claims = {
        "sub": email.lower(),
        "name": name,
        "iat": now,
        "exp": now + dt.timedelta(hours=settings.jwt_ttl_hours),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


class User:
    def __init__(self, email: str, name: str, is_admin: bool):
        self.email, self.name, self.is_admin = email, name, is_admin


def current_user(request: Request, settings: Settings = Depends(get_settings)) -> User:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in required")
    try:
        claims = jwt.decode(header[7:], settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(401, "Session expired, please sign in again") from e
    email = claims["sub"]
    return User(email, claims.get("name", ""), email in settings.admin_email_set)


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admins only")
    return user
