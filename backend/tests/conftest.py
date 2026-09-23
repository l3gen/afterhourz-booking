import datetime as dt
import os

# Must be set before app.config is imported anywhere.
os.environ.update(
    ENV="local",
    DEV_LOGIN_ENABLED="true",
    ADMIN_EMAILS="owner@example.com",
    AWS_ACCESS_KEY_ID="testing",
    AWS_SECRET_ACCESS_KEY="testing",
    AWS_DEFAULT_REGION="us-east-1",
    TABLE_NAME="test-table",
)

import boto3  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from moto import mock_aws  # noqa: E402

from app import deps, timeutil  # noqa: E402
from app.main import app  # noqa: E402
from app.repo import Repo  # noqa: E402
from app.schema import TABLE_DEFINITION  # noqa: E402

# Monday 2026-09-21 12:00 in New York (16:00 UTC). Tue 22nd is the next open day.
FROZEN_NOW = dt.datetime(2026, 9, 21, 16, 0, tzinfo=dt.UTC)
TUESDAY = "2026-09-22"
MONDAY = "2026-09-21"


class FakePayments:
    def __init__(self):
        self.enabled = False
        self.checkouts: list[dict] = []
        self.refunds: list[str] = []

    def create_checkout(self, appt, now_epoch):
        self.checkouts.append(appt)
        return f"cs_{appt['id'][:6]}", f"https://checkout.test/{appt['id']}"

    def refund(self, pi):
        self.refunds.append(pi)

    def parse_event(self, payload, signature):
        import json

        if signature != "valid":
            raise ValueError("bad signature")
        return json.loads(payload)


class FakeNotifier:
    def __init__(self):
        self.confirmations, self.cancellations = [], []

    def send_confirmation(self, appt):
        self.confirmations.append(appt["id"])

    def send_cancellation(self, appt, refunded):
        self.cancellations.append((appt["id"], refunded))


class FakeCalendar:
    enabled = True

    def __init__(self):
        self.created, self.deleted = [], []

    def create_event(self, appt):
        self.created.append(appt["id"])
        return f"evt_{appt['id'][:6]}"

    def delete_event(self, event_id):
        self.deleted.append(event_id)


@pytest.fixture
def repo():
    with mock_aws():
        res = boto3.resource("dynamodb", region_name="us-east-1")
        res.create_table(TableName="test-table", **TABLE_DEFINITION)
        yield Repo(res, "test-table")


@pytest.fixture
def fakes(repo):
    return type("Fakes", (), {"payments": FakePayments(), "notifier": FakeNotifier(), "calendar": FakeCalendar()})


@pytest.fixture
def now(monkeypatch):
    holder = {"now": FROZEN_NOW}
    monkeypatch.setattr(timeutil, "now_utc", lambda: holder["now"])
    return holder


@pytest.fixture
def client(repo, fakes, now):
    app.dependency_overrides[deps.get_repo] = lambda: repo
    app.dependency_overrides[deps.get_payments] = lambda: fakes.payments
    app.dependency_overrides[deps.get_notifier] = lambda: fakes.notifier
    app.dependency_overrides[deps.get_calendar] = lambda: fakes.calendar
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client, email="client@example.com", name="Client One") -> dict:
    r = client.post("/api/auth/dev-login", json={"email": email, "name": name})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def user_h(client):
    return login(client)


@pytest.fixture
def other_h(client):
    return login(client, "other@example.com", "Other Person")


@pytest.fixture
def admin_h(client):
    return login(client, "owner@example.com", "Owner")


def book(client, headers, time="10:00", service="haircut", date=TUESDAY, phone="305-555-0100"):
    return client.post(
        "/api/appointments",
        headers=headers,
        json={"service_id": service, "date": date, "time": time, "phone": phone},
    )
