import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query

from app import timeutil
from app.availability import available_times, open_days
from app.catalog import SERVICES, get_service
from app.config import Settings, get_settings
from app.deps import get_payments, get_repo
from app.payments import Payments
from app.repo import Repo

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/health")
def health():
    """ALB target-group health check. Deliberately does not touch the database."""
    return {"status": "ok"}


@router.get("/site-config")
def site_config(settings: Settings = Depends(get_settings), payments: Payments = Depends(get_payments)):
    """Runtime settings the SPA needs. Nothing secret: the Google client ID is public by design."""
    return {
        "google_client_id": settings.google_client_id,
        "payments_enabled": payments.enabled,
        "cancel_window_hours": settings.cancel_window_hours,
    }


@router.get("/services")
def services():
    return [s.public() for s in SERVICES]


@router.get("/open-days")
def days(repo: Repo = Depends(get_repo), settings: Settings = Depends(get_settings)):
    tz = timeutil.tz_of(settings.timezone)
    now_local = timeutil.now_utc().astimezone(tz)
    return {"days": open_days(repo.get_config(), now_local, settings.max_advance_days)}


@router.get("/availability")
def availability(
    service_id: str = Query(max_length=40),
    date: dt.date = Query(),
    repo: Repo = Depends(get_repo),
    settings: Settings = Depends(get_settings),
):
    service = get_service(service_id)
    if not service:
        raise HTTPException(404, "Unknown service")
    tz = timeutil.tz_of(settings.timezone)
    now = timeutil.now_utc()
    taken = repo.taken_slots(date.isoformat(), int(now.timestamp()))
    times = available_times(
        repo.get_config(),
        service,
        date,
        now.astimezone(tz),
        taken,
        settings.lead_time_minutes,
        settings.max_advance_days,
        tz,
    )
    return {"date": date.isoformat(), "times": times}
