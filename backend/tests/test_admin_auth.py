import datetime as dt
import hashlib
import hmac
import json
import time

import jwt
import pytest
import stripe

from app import auth
from app.config import Settings
from app.payments import Payments
from tests.conftest import TUESDAY, book


def test_admin_routes_forbidden_for_normal_users(client, user_h):
    assert (
        client.get("/api/admin/appointments", params={"from": TUESDAY, "to": TUESDAY}, headers=user_h).status_code
        == 403
    )
    assert client.get("/api/admin/config", headers=user_h).status_code == 403
    assert client.get("/api/admin/config").status_code == 401


def test_admin_sees_all_bookings_for_range(client, admin_h, user_h, other_h):
    book(client, user_h, time="10:00")
    book(client, other_h, time="11:00")
    r = client.get("/api/admin/appointments", params={"from": TUESDAY, "to": TUESDAY}, headers=admin_h)
    assert [a["time"] for a in r.json()] == ["10:00", "11:00"]


def test_admin_range_limit(client, admin_h):
    r = client.get("/api/admin/appointments", params={"from": "2026-09-01", "to": "2026-12-31"}, headers=admin_h)
    assert r.status_code == 400


def test_admin_cancel_always_refunds(client, admin_h, user_h, fakes):
    fakes.payments.enabled = True
    appt = book(client, user_h, time="10:00").json()["appointment"]  # inside client's 24h window
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {"metadata": {"appointment_id": appt["id"]}, "payment_status": "paid", "payment_intent": "pi_a"}
        },
    }
    client.post("/api/webhooks/stripe", content=json.dumps(event), headers={"stripe-signature": "valid"})
    r = client.post(f"/api/admin/appointments/{appt['id']}/cancel", headers=admin_h)
    assert r.status_code == 200 and r.json()["refunded"] is True
    assert fakes.notifier.cancellations == [(appt["id"], True)]


def test_admin_can_close_a_day_and_change_hours(client, admin_h, user_h):
    cfg = client.get("/api/admin/config", headers=admin_h).json()
    cfg["closed_dates"] = [TUESDAY]
    assert client.put("/api/admin/config", json=cfg, headers=admin_h).status_code == 200
    assert client.get("/api/availability", params={"service_id": "haircut", "date": TUESDAY}).json()["times"] == []
    assert book(client, user_h).status_code == 409

    cfg["closed_dates"] = []
    cfg["hours"]["1"] = {"open": "12:00", "close": "14:00"}
    client.put("/api/admin/config", json=cfg, headers=admin_h)
    times = client.get("/api/availability", params={"service_id": "haircut", "date": TUESDAY}).json()["times"]
    assert times[0] == "12:00" and times[-1] == "13:30"


@pytest.mark.parametrize(
    "hours",
    [
        {"1": {"open": "10:15", "close": "19:00"}},  # off the 30 min grid
        {"1": {"open": "19:00", "close": "10:00"}},  # open after close
        {"9": {"open": "10:00", "close": "19:00"}},  # bad weekday
    ],
)
def test_invalid_hours_rejected(client, admin_h, hours):
    r = client.put("/api/admin/config", json={"hours": hours, "closed_dates": []}, headers=admin_h)
    assert r.status_code == 422


# ------------------------------------------------------------------- auth
def test_google_login_flow(client, monkeypatch):
    monkeypatch.setattr(
        auth,
        "verify_google_credential",
        lambda cred, s: {"email": "Owner@Example.com", "name": "The Owner", "email_verified": True},
    )
    r = client.post("/api/auth/google", json={"credential": "x" * 20})
    assert r.status_code == 200
    assert r.json()["user"] == {"email": "owner@example.com", "name": "The Owner", "is_admin": True}
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"})
    assert me.json()["is_admin"] is True


def test_google_login_rejects_when_unconfigured(client):
    r = client.post("/api/auth/google", json={"credential": "x" * 20})
    assert r.status_code == 503  # GOOGLE_CLIENT_ID not set in tests


def test_expired_and_forged_tokens_rejected(client, now):
    s = Settings()
    good = auth.issue_token("a@example.com", "A", s)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {good}"}).status_code == 200
    real_now = dt.datetime.now(dt.UTC)  # PyJWT checks exp against the real clock, not our frozen one
    forged = jwt.encode(
        {"sub": "owner@example.com", "exp": real_now + dt.timedelta(hours=1)},
        "wrong-secret-wrong-secret-wrong!",
        algorithm="HS256",
    )
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    expired = jwt.encode(
        {"sub": "a@example.com", "exp": real_now - dt.timedelta(hours=1)}, s.jwt_secret, algorithm="HS256"
    )
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_insecure_config_refused_outside_local():
    with pytest.raises(ValueError):
        Settings(env="prod", dev_login_enabled=False)  # default JWT secret
    with pytest.raises(ValueError):
        Settings(env="prod", jwt_secret="x" * 40, dev_login_enabled=True)
    with pytest.raises(ValueError):
        Settings(env="local", payments_enabled=True)  # missing stripe keys
    Settings(env="prod", jwt_secret="x" * 40, dev_login_enabled=False)  # fine


def test_dev_login_disabled_returns_404(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "dev_login_enabled", False)
    assert client.post("/api/auth/dev-login", json={"email": "a@example.com"}).status_code == 404


# ------------------------------------------------- real Stripe signature check
def test_real_stripe_signature_verification():
    secret = "whsec_test_secret"
    p = Payments(Settings(payments_enabled=True, stripe_secret_key="sk_test_x", stripe_webhook_secret=secret))
    payload = json.dumps(
        {"id": "evt_1", "object": "event", "type": "checkout.session.completed", "data": {"object": {"id": "cs_1"}}}
    ).encode()
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    event = p.parse_event(payload, f"t={ts},v1={sig}")
    assert event["type"] == "checkout.session.completed"
    with pytest.raises(stripe.SignatureVerificationError):
        p.parse_event(payload, f"t={ts},v1={'0' * 64}")
