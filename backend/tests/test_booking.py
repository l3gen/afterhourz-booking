import datetime as dt
import json

from tests.conftest import TUESDAY, book


def test_booking_requires_login(client):
    r = client.post(
        "/api/appointments", json={"service_id": "haircut", "date": TUESDAY, "time": "10:00", "phone": "3055550100"}
    )
    assert r.status_code == 401


def test_book_without_payments_confirms_immediately(client, user_h, fakes):
    r = book(client, user_h)
    assert r.status_code == 201
    body = r.json()
    assert body["checkout_url"] is None
    assert body["appointment"]["status"] == "confirmed"
    assert body["appointment"]["phone"] == "+13055550100"
    # side effects run after the response (TestClient executes background tasks)
    assert fakes.notifier.confirmations == [body["appointment"]["id"]]
    assert fakes.calendar.created == [body["appointment"]["id"]]


def test_same_time_cannot_be_booked_twice(client, user_h, other_h):
    assert book(client, user_h, time="14:00").status_code == 201
    r = book(client, other_h, time="14:00")
    assert r.status_code == 409


def test_overlapping_long_service_is_rejected(client, user_h, other_h):
    assert book(client, user_h, time="11:00").status_code == 201
    assert book(client, other_h, time="10:30", service="cut-beard").status_code == 409
    assert book(client, other_h, time="10:00", service="cut-beard").status_code == 201


def test_slot_transaction_is_atomic(client, user_h, other_h, repo):
    """If the second slot of a 60 min booking is taken, the first must NOT be left held."""
    assert book(client, user_h, time="11:00").status_code == 201
    # Bypass API validation to hit the transaction directly.
    from app.repo import SlotTaken

    appt = {
        "id": "x" * 32,
        "date": TUESDAY,
        "time": "10:30",
        "duration_min": 60,
        "customer_email": "z@example.com",
        "status": "confirmed",
    }
    try:
        repo.create(appt, now_epoch=0)
        raise AssertionError("expected SlotTaken")
    except SlotTaken:
        pass
    assert "10:30" not in repo.taken_slots(TUESDAY, 0)
    assert repo.get("x" * 32) is None


def test_validation(client, user_h):
    bad_time = client.post(
        "/api/appointments",
        headers=user_h,
        json={"service_id": "haircut", "date": TUESDAY, "time": "25:99", "phone": "3055550100"},
    )
    assert bad_time.status_code == 422
    bad_phone = client.post(
        "/api/appointments",
        headers=user_h,
        json={"service_id": "haircut", "date": TUESDAY, "time": "10:00", "phone": "abc"},
    )
    assert bad_phone.status_code == 422
    assert book(client, user_h, service="nope").status_code == 404
    assert book(client, user_h, time="09:00").status_code == 409  # before opening
    assert book(client, user_h, time="10:15").status_code == 409  # off the slot grid


def test_my_appointments_only_shows_own(client, user_h, other_h):
    book(client, user_h, time="10:00")
    book(client, other_h, time="12:00")
    mine = client.get("/api/appointments/mine", headers=user_h).json()
    assert len(mine) == 1 and mine[0]["customer_email"] == "client@example.com"


def test_cannot_read_someone_elses_appointment(client, user_h, other_h):
    appt_id = book(client, user_h).json()["appointment"]["id"]
    assert client.get(f"/api/appointments/{appt_id}", headers=other_h).status_code == 404
    assert client.get(f"/api/appointments/{appt_id}", headers=user_h).status_code == 200


# ----------------------------------------------------------------- deposits
def test_deposit_flow_hold_then_webhook_confirms(client, user_h, fakes):
    fakes.payments.enabled = True
    r = book(client, user_h, time="15:00")
    assert r.status_code == 201
    appt = r.json()["appointment"]
    assert appt["status"] == "pending_payment" and appt["deposit_cents"] == 1000
    assert r.json()["checkout_url"].startswith("https://checkout.test/")
    assert fakes.notifier.confirmations == []  # nothing sent until paid

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {"metadata": {"appointment_id": appt["id"]}, "payment_status": "paid", "payment_intent": "pi_123"}
        },
    }
    w = client.post("/api/webhooks/stripe", content=json.dumps(event), headers={"stripe-signature": "valid"})
    assert w.status_code == 200
    got = client.get(f"/api/appointments/{appt['id']}", headers=user_h).json()
    assert got["status"] == "confirmed" and got["payment_intent_id"] == "pi_123"
    assert fakes.notifier.confirmations == [appt["id"]]
    assert fakes.calendar.created == [appt["id"]]

    # Stripe retries webhooks; a duplicate must be harmless.
    client.post("/api/webhooks/stripe", content=json.dumps(event), headers={"stripe-signature": "valid"})
    assert fakes.payments.refunds == []


def test_webhook_rejects_bad_signature(client):
    r = client.post("/api/webhooks/stripe", content="{}", headers={"stripe-signature": "forged"})
    assert r.status_code == 400


def test_unpaid_hold_expires_and_frees_the_slot(client, user_h, other_h, fakes, now):
    fakes.payments.enabled = True
    assert book(client, user_h, time="16:00").status_code == 201
    assert book(client, other_h, time="16:00").status_code == 409  # held
    now["now"] += dt.timedelta(minutes=40)
    assert book(client, other_h, time="16:00").status_code == 201  # hold lapsed


def test_late_payment_after_slot_lost_is_refunded(client, user_h, other_h, fakes, now):
    fakes.payments.enabled = True
    first = book(client, user_h, time="16:00").json()["appointment"]
    now["now"] += dt.timedelta(minutes=40)
    fakes.payments.enabled = False  # second client books without deposit
    assert book(client, other_h, time="16:00").status_code == 201
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"appointment_id": first["id"]},
                "payment_status": "paid",
                "payment_intent": "pi_late",
            }
        },
    }
    client.post("/api/webhooks/stripe", content=json.dumps(event), headers={"stripe-signature": "valid"})
    assert fakes.payments.refunds == ["pi_late"]
    assert client.get(f"/api/appointments/{first['id']}", headers=user_h).json()["status"] != "confirmed"


def test_stripe_session_expired_releases_slot(client, user_h, other_h, fakes):
    fakes.payments.enabled = True
    appt = book(client, user_h, time="13:00").json()["appointment"]
    event = {"type": "checkout.session.expired", "data": {"object": {"metadata": {"appointment_id": appt["id"]}}}}
    client.post("/api/webhooks/stripe", content=json.dumps(event), headers={"stripe-signature": "valid"})
    assert book(client, other_h, time="13:00").status_code == 201


# ------------------------------------------------------------------ cancel
def _pay(client, fakes, appt_id, pi="pi_1"):
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"appointment_id": appt_id}, "payment_status": "paid", "payment_intent": pi}},
    }
    client.post("/api/webhooks/stripe", content=json.dumps(event), headers={"stripe-signature": "valid"})


def test_cancel_outside_window_refunds_and_frees_slot(client, user_h, other_h, fakes):
    fakes.payments.enabled = True
    appt = book(client, user_h, time="15:00").json()["appointment"]  # ~27h away
    _pay(client, fakes, appt["id"])
    r = client.post(f"/api/appointments/{appt['id']}/cancel", headers=user_h)
    assert r.status_code == 200 and r.json()["refunded"] is True
    assert fakes.payments.refunds == ["pi_1"]
    assert fakes.calendar.deleted == [f"evt_{appt['id'][:6]}"]
    assert book(client, other_h, time="15:00").status_code == 201


def test_late_cancel_forfeits_deposit(client, user_h, fakes, now):
    fakes.payments.enabled = True
    appt = book(client, user_h, time="10:00").json()["appointment"]  # 22h away, inside 24h window
    _pay(client, fakes, appt["id"])
    r = client.post(f"/api/appointments/{appt['id']}/cancel", headers=user_h)
    assert r.status_code == 200 and r.json()["refunded"] is False
    assert fakes.payments.refunds == []


def test_cannot_cancel_someone_elses(client, user_h, other_h):
    appt = book(client, user_h).json()["appointment"]
    assert client.post(f"/api/appointments/{appt['id']}/cancel", headers=other_h).status_code == 404


def test_cannot_cancel_twice(client, user_h):
    appt = book(client, user_h).json()["appointment"]
    assert client.post(f"/api/appointments/{appt['id']}/cancel", headers=user_h).status_code == 200
    assert client.post(f"/api/appointments/{appt['id']}/cancel", headers=user_h).status_code == 409
