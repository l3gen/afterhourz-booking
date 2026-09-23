import datetime as dt

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app import auth, timeutil
from app.availability import validate_config
from app.calendar_sync import CalendarSync
from app.config import Settings, get_settings
from app.deps import get_calendar, get_notifier, get_payments, get_repo
from app.models import ConfigUpdate
from app.notifications import Notifier
from app.payments import Payments
from app.repo import Repo
from app.routers.appointments import cancel_and_refund

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.admin_user)])


@router.get("/appointments")
def list_appointments(
    start: dt.date = Query(alias="from"),
    end: dt.date = Query(alias="to"),
    repo: Repo = Depends(get_repo),
):
    if end < start or (end - start).days > 31:
        raise HTTPException(400, "Range must be 0-31 days")
    now_epoch = int(timeutil.now_utc().timestamp())
    return repo.list_range(start.isoformat(), end.isoformat(), now_epoch)


@router.post("/appointments/{appt_id}/cancel")
def admin_cancel(
    appt_id: str,
    background: BackgroundTasks,
    admin: auth.User = Depends(auth.admin_user),
    repo: Repo = Depends(get_repo),
    payments: Payments = Depends(get_payments),
    notifier: Notifier = Depends(get_notifier),
    calendar: CalendarSync = Depends(get_calendar),
    settings: Settings = Depends(get_settings),
):
    appt = repo.get(appt_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")
    if appt["status"] not in ("confirmed", "pending_payment"):
        raise HTTPException(409, f"Appointment is already {appt['status']}")
    # Shop-initiated cancellations always refund the deposit.
    cancelled, refunded = cancel_and_refund(appt, admin.email, True, repo, payments, settings)
    background.add_task(calendar.delete_event, appt.get("calendar_event_id"))
    background.add_task(notifier.send_cancellation, cancelled, refunded)
    return {"appointment": cancelled, "refunded": refunded}


@router.get("/config")
def get_config(repo: Repo = Depends(get_repo)):
    return repo.get_config()


@router.put("/config")
def put_config(body: ConfigUpdate, repo: Repo = Depends(get_repo)):
    try:
        validate_config(body.hours, body.closed_dates)
    except (ValueError, KeyError) as e:
        raise HTTPException(422, f"Invalid hours: {e}") from None
    repo.put_config(body.hours, body.closed_dates)
    return repo.get_config()
