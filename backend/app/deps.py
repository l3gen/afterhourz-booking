"""Dependency providers. Singletons are cached; tests override them via
app.dependency_overrides."""

from functools import lru_cache

import boto3

from app.calendar_sync import CalendarSync
from app.config import get_settings
from app.notifications import Notifier
from app.payments import Payments
from app.repo import Repo


@lru_cache
def get_repo() -> Repo:
    s = get_settings()
    kwargs = {"region_name": s.aws_region}
    if s.dynamodb_endpoint_url:
        kwargs["endpoint_url"] = s.dynamodb_endpoint_url
    return Repo(boto3.resource("dynamodb", **kwargs), s.table_name)


@lru_cache
def get_notifier() -> Notifier:
    return Notifier(get_settings())


@lru_cache
def get_calendar() -> CalendarSync:
    return CalendarSync(get_settings())


@lru_cache
def get_payments() -> Payments:
    return Payments(get_settings())
