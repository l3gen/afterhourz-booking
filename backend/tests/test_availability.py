from tests.conftest import MONDAY, TUESDAY, book


def test_services_listed(client):
    r = client.get("/api/services")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert {"haircut", "cut-beard"} <= ids


def test_site_config_exposes_only_public_settings(client, fakes):
    fakes.payments.enabled = True
    cfg = client.get("/api/site-config").json()
    assert cfg == {"google_client_id": "", "payments_enabled": True, "cancel_window_hours": 24}


def test_health_needs_no_db(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_open_day_lists_all_half_hour_starts(client):
    r = client.get("/api/availability", params={"service_id": "haircut", "date": TUESDAY})
    times = r.json()["times"]
    assert times[0] == "10:00" and times[-1] == "18:30"
    assert len(times) == 18


def test_long_service_cannot_start_in_last_slot(client):
    times = client.get("/api/availability", params={"service_id": "cut-beard", "date": TUESDAY}).json()["times"]
    assert times[-1] == "18:00"


def test_closed_days_have_no_times(client):
    # Monday is closed by default; so is Sunday 2026-09-27.
    for d in (MONDAY, "2026-09-27"):
        assert client.get("/api/availability", params={"service_id": "haircut", "date": d}).json()["times"] == []


def test_booked_slots_disappear_and_overlaps_are_blocked(client, user_h):
    assert book(client, user_h, time="11:00").status_code == 201
    haircut = client.get("/api/availability", params={"service_id": "haircut", "date": TUESDAY}).json()["times"]
    assert "11:00" not in haircut and "10:30" in haircut
    # A 60 minute service starting 10:30 would run into the 11:00 booking.
    long = client.get("/api/availability", params={"service_id": "cut-beard", "date": TUESDAY}).json()["times"]
    assert "10:30" not in long and "11:00" not in long and "10:00" in long


def test_lead_time_and_past_dates(client, now):
    import datetime as dt

    # Tuesday 10:30 local; lead time is 2h, so 12:30 is the earliest bookable start.
    now["now"] = dt.datetime(2026, 9, 22, 14, 30, tzinfo=dt.UTC)
    times = client.get("/api/availability", params={"service_id": "haircut", "date": TUESDAY}).json()["times"]
    assert times[0] == "12:30"
    assert client.get("/api/availability", params={"service_id": "haircut", "date": MONDAY}).json()["times"] == []


def test_beyond_max_advance_is_empty(client):
    far = "2026-12-01"
    assert client.get("/api/availability", params={"service_id": "haircut", "date": far}).json()["times"] == []


def test_unknown_service_404(client):
    assert client.get("/api/availability", params={"service_id": "nope", "date": TUESDAY}).status_code == 404


def test_open_days_skip_closed_days(client):
    days = client.get("/api/open-days").json()["days"]
    assert MONDAY not in days and TUESDAY in days
