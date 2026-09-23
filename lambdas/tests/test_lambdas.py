import datetime as dt
import os
import sys
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import boto3
import pytest
from moto import mock_aws

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")

ROOT = os.path.join(os.path.dirname(__file__), "..")
for name in ("reminders", "reaper", "cost_analyst"):
    sys.path.insert(0, os.path.join(ROOT, name))

# Each handler module is called handler.py, so import by file path to avoid name clashes.
import importlib.util  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_handler", os.path.join(ROOT, name, "handler.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


reminders, reaper, analyst = load("reminders"), load("reaper"), load("cost_analyst")

# The backend's table definition is the single source of truth for the schema.
sys.path.insert(0, os.path.join(ROOT, "..", "backend"))
from app.schema import TABLE_DEFINITION  # noqa: E402


# ----------------------------------------------------------------- reminders
@pytest.fixture
def table():
    with mock_aws():
        res = boto3.resource("dynamodb", region_name="us-east-1")
        t = res.create_table(TableName="t", **TABLE_DEFINITION)
        os.environ["TABLE_NAME"] = "t"
        yield t


def put_appt(table, id_, date, status="confirmed", **extra):
    table.put_item(
        Item={
            "pk": f"APPT#{id_}",
            "sk": "META",
            "id": id_,
            "date": date,
            "time": "10:00",
            "gsi2pk": f"DAY#{date}",
            "gsi2sk": f"10:00#{id_}",
            "status": status,
            "customer_email": f"{id_}@example.com",
            "service_name": "Haircut",
            "phone": "+13055550100",
            **extra,
        }
    )


def test_reminders_only_for_tomorrow_confirmed_and_unsent(table, monkeypatch):
    monkeypatch.setenv("SES_FROM", "bookings@example.com")
    monkeypatch.setenv("SMS_ENABLED", "true")
    now = dt.datetime(2026, 9, 21, 16, 0, tzinfo=ZoneInfo("America/New_York"))
    put_appt(table, "a", "2026-09-22")
    put_appt(table, "b", "2026-09-22", status="cancelled")
    put_appt(table, "c", "2026-09-22", reminder_sent=True)
    put_appt(table, "d", "2026-09-23")  # day after tomorrow
    ses, sns = MagicMock(), MagicMock()
    out = reminders.handler({}, None, table=table, ses=ses, sns=sns, now=now)
    assert out == {"date": "2026-09-22", "sent": 1}
    assert ses.send_email.call_count == 1
    assert ses.send_email.call_args.kwargs["Destination"]["ToAddresses"] == ["a@example.com"]
    assert sns.publish.call_count == 1
    # idempotent: a second run sends nothing
    assert reminders.handler({}, None, table=table, ses=MagicMock(), sns=MagicMock(), now=now)["sent"] == 0


# -------------------------------------------------------------------- reaper
ECS_ARN = "arn:aws:ecs:us-east-1:123456789012:service/afterhourz-dev/api"
ALB_ARN = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/afterhourz-dev/abc123"


def _reaper_clients():
    tagging = MagicMock()
    tagging.get_resources.return_value = {
        "ResourceTagMappingList": [{"ResourceARN": ECS_ARN}, {"ResourceARN": ALB_ARN}],
        "PaginationToken": "",
    }
    return tagging, MagicMock(), MagicMock(), MagicMock()


def test_reaper_destroy_mode_acts_on_tagged_resources(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("REAPER_MODE", "destroy")
    monkeypatch.setenv("ALERT_TOPIC_ARN", "arn:aws:sns:us-east-1:1:alerts")
    tagging, ecs, elb, sns = _reaper_clients()
    out = reaper.handler({}, None, tagging=tagging, ecs=ecs, elb=elb, sns=sns)
    ecs.update_service.assert_called_once_with(cluster="afterhourz-dev", service="api", desiredCount=0)
    elb.delete_load_balancer.assert_called_once_with(LoadBalancerArn=ALB_ARN)
    assert len(out["actions"]) == 2 and sns.publish.called
    # the tag filter must scope by Project, Env and Ephemeral
    keys = {f["Key"] for f in tagging.get_resources.call_args.kwargs["TagFilters"]}
    assert keys == {"Project", "Env", "Ephemeral"}


def test_reaper_notify_mode_never_touches_anything(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("REAPER_MODE", "notify")
    tagging, ecs, elb, sns = _reaper_clients()
    out = reaper.handler({}, None, tagging=tagging, ecs=ecs, elb=elb, sns=sns)
    assert out["dry_run"] is True
    ecs.update_service.assert_not_called()
    elb.delete_load_balancer.assert_not_called()


def test_reaper_dry_run_flag_overrides_destroy_mode(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("REAPER_MODE", "destroy")
    tagging, ecs, elb, sns = _reaper_clients()
    reaper.handler({"dry_run": True}, None, tagging=tagging, ecs=ecs, elb=elb, sns=sns)
    ecs.update_service.assert_not_called()


# ------------------------------------------------------------------ analyst
def _ce(daily):
    ce = MagicMock()
    days = sorted({d for s in daily.values() for d in s})
    ce.get_cost_and_usage.return_value = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": d},
                "Groups": [
                    {"Keys": [svc], "Metrics": {"UnblendedCost": {"Amount": str(series[d])}}}
                    for svc, series in daily.items()
                    if d in series
                ],
            }
            for d in days
        ]
    }
    return ce


SPIKY = {
    "Amazon Elastic Load Balancing": {f"2026-09-{d:02d}": 0.5 for d in range(14, 21)} | {"2026-09-20": 6.0},
    "Amazon DynamoDB": {f"2026-09-{d:02d}": 0.01 for d in range(14, 21)},
}


def test_flag_spikes_finds_the_alb():
    flags = analyst.flag_spikes(SPIKY)
    assert len(flags) == 1 and "Load Balancing" in flags[0]


def test_analyst_emails_ai_summary_and_takes_no_action(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setenv("ALERT_TOPIC_ARN", "arn:aws:sns:us-east-1:1:alerts")
    monkeypatch.setenv("MONTHLY_BUDGET_USD", "40")
    bedrock, sns = MagicMock(), MagicMock()
    bedrock.converse.return_value = {
        "output": {
            "message": {
                "content": [
                    {
                        "text": 'Sure:\n{"severity":"watch","summary":"ALB spiked.","top_drivers":["ALB"],"recommended_actions":["Destroy the dev stack"]}'
                    }
                ]
            }
        }
    }
    out = analyst.handler({}, None, ce=_ce(SPIKY), bedrock=bedrock, sns=sns, today=dt.date(2026, 9, 21))
    assert out["severity"] == "watch" and out["spikes"]
    msg = sns.publish.call_args.kwargs["Message"]
    assert "ALB spiked." in msg and "No automatic action was taken" in msg


def test_analyst_survives_bedrock_outage(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setenv("ALERT_TOPIC_ARN", "arn:aws:sns:us-east-1:1:alerts")
    bedrock, sns = MagicMock(), MagicMock()
    bedrock.converse.side_effect = RuntimeError("AccessDenied: model access not enabled")
    out = analyst.handler({}, None, ce=_ce(SPIKY), bedrock=bedrock, sns=sns, today=dt.date(2026, 9, 21))
    assert out["severity"] == "watch"  # falls back to rule-based severity
    assert "AI analysis unavailable" in sns.publish.call_args.kwargs["Message"]
