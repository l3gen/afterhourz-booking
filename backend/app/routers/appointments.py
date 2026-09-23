import datetime as dt
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app import auth, timeutil
from app.availability import available_times
from app.calendar_sync import CalendarSync
from app.catalog import get_service
from app.config import Settings, get_settings
from app.deps import get_calendar, get_notifier, get_payments, get_repo
from app.models import AppointmentCreate
from app.notifications import Notifier
from app.payments import HOLD_SECONDS, Payments
from app.repo import NotFound, Repo, SlotTaken

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/appointments", tags=["appointments"])


def post_confirm(appt_id: str, repo: Repo, notifier: Notifier, calendar: CalendarSync) -> None:
    """Side effects after a booking becomes confirmed. Never raises."""
    try:
        appt = repo.get(appt_id)
        if not appt:
            return
        event_id = calendar.create_event(appt)
        if event_id:
            repo.set_fields(appt_id, calendar_event_id=event_id)
        notifier.send_confirmation(appt)
    except Exception:  # noqa: BLE001
        log.exception("post-confirm side effects failed for %s", appt_id)


def cancel_and_refund(
    appt: dict, by: str, force_refund: bool, repo: Repo, payments: Payments, settings: Settings
) -> tuple[dict, bool]:
    """Cancel, free the slots, and refund the deposit if policy allows. Returns (appt, refunded)."""
    now = timeutil.now_utc()
    tz = timeutil.tz_of(settings.timezone)
    start = timeutil.local_dt(appt["date"], appt["time"], tz)
    hours_ahead = (start - now).total_seconds() / 3600
    was_paid = bool(appt.get("payment_intent_id"))
    cancelled = repo.cancel(appt["id"], by, now.isoformat())
    refunded = False
    if was_paid and (force_refund or hours_ahead >= settings.cancel_window_hours):
        try:
            payments.refund(appt["payment_intent_id"])
            repo.set_fields(appt["id"], refunded=True)
            refunded = True
        except Exception:  # noqa: BLE001
            log.exception("refund failed for %s - refund manually in Stripe", appt["id"])
    return cancelled, refunded


@router.post("", status_code=201)
def create_appointment(
    body: AppointmentCreate,
    background: BackgroundTasks,
    user: auth.User = Depends(auth.current_user),
    repo: Repo = Depends(get_repo),
    payments: Payments = Depends(get_payments),
    notifier: Notifier = Depends(get_notifier),
    calendar: CalendarSync = Depends(get_calendar),
    settings: Settings = Depends(get_settings),
):
    service = get_service(body.service_id)
    if not service:
        raise HTTPException(404, "Unknown service")

    now = timeutil.now_utc()
    now_epoch = int(now.timestamp())
    tz = timeutil.tz_of(settings.timezone)
    date_s = body.date.isoformat()

    # Re-validate against live availability (the client's list may be stale).
    times = available_times(
        repo.get_config(),
        service,
        body.date,
        now.astimezone(tz),
        repo.taken_slots(date_s, now_epoch),
        settings.lead_time_minutes,
        settings.max_advance_days,
        tz,
    )
    if body.time not in times:
        raise HTTPException(409, "That time is no longer available. Please pick another.")

    deposit = service.deposit_cents if payments.enabled else 0
    start = timeutil.local_dt(date_s, body.time, tz)
    appt = {
        "id": uuid.uuid4().hex,
        "service_id": service.id,
        "service_name": service.name,
        "duration_min": service.duration_min,
        "price_cents": service.price_cents,
        "deposit_cents": deposit,
        "date": date_s,
        "time": body.time,
        "start_utc": start.astimezone(dt.UTC).isoformat(),
        "customer_email": user.email,
        "customer_name": user.name,
        "phone": body.phone,
        "notes": body.notes,
        "source": body.source,
        "created_at": now.isoformat(),
        "status": "pending_payment" if deposit else "confirmed",
    }
    if deposit:
        appt["hold_expires_at"] = now_epoch + HOLD_SECONDS

    try:
        repo.create(appt, now_epoch)
    except SlotTaken:
        raise HTTPException(409, "That time was just taken. Please pick another.") from None

    checkout_url = None
    if deposit:
        try:
            session_id, checkout_url = payments.create_checkout(appt, now_epoch)
            repo.set_fields(appt["id"], stripe_session_id=session_id)
        except Exception:  # noqa: BLE001
            log.exception("stripe checkout failed")
            repo.cancel(appt["id"], "system", now.isoformat())  # release the hold
            raise HTTPException(502, "Payment provider unavailable, please try again.") from None
    else:
        background.add_task(post_confirm, appt["id"], repo, notifier, calendar)

    return {"appointment": repo.get(appt["id"], now_epoch), "checkout_url": checkout_url}


@router.get("/mine")
def my_appointments(user: auth.User = Depends(auth.current_user), repo: Repo = Depends(get_repo)):
    return repo.list_for_user(user.email, int(timeutil.now_utc().timestamp()))


@router.get("/{appt_id}")
def get_appointment(appt_id: str, user: auth.User = Depends(auth.current_user), repo: Repo = Depends(get_repo)):
    appt = repo.get(appt_id, int(timeutil.now_utc().timestamp()))
    if not appt or (appt["customer_email"] != user.email and not user.is_admin):
        raise HTTPException(404, "Appointment not found")
    return appt


@router.post("/{appt_id}/cancel")
def cancel_appointment(
    appt_id: str,
    background: BackgroundTasks,
    user: auth.User = Depends(auth.current_user),
    repo: Repo = Depends(get_repo),
    payments: Payments = Depends(get_payments),
    notifier: Notifier = Depends(get_notifier),
    calendar: CalendarSync = Depends(get_calendar),
    settings: Settings = Depends(get_settings),
):
    appt = repo.get(appt_id)
    if not appt or appt["customer_email"] != user.email:
        raise HTTPException(404, "Appointment not found")
    if appt["status"] not in ("confirmed", "pending_payment"):
        raise HTTPException(409, f"Appointment is already {appt['status']}")
    try:
        cancelled, refunded = cancel_and_refund(appt, user.email, False, repo, payments, settings)
    except NotFound:
        raise HTTPException(404, "Appointment not found") from None
    background.add_task(calendar.delete_event, appt.get("calendar_event_id"))
    background.add_task(notifier.send_cancellation, cancelled, refunded)
    return {"appointment": cancelled, "refunded": refunded}
