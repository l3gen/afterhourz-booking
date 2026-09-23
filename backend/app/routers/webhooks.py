import logging

import stripe
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app import timeutil
from app.calendar_sync import CalendarSync
from app.deps import get_calendar, get_notifier, get_payments, get_repo
from app.notifications import Notifier
from app.payments import Payments
from app.repo import ConfirmFailed, NotFound, Repo
from app.routers.appointments import post_confirm

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    background: BackgroundTasks,
    repo: Repo = Depends(get_repo),
    payments: Payments = Depends(get_payments),
    notifier: Notifier = Depends(get_notifier),
    calendar: CalendarSync = Depends(get_calendar),
):
    payload = await request.body()
    try:
        event = payments.parse_event(payload, request.headers.get("stripe-signature", ""))
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid signature") from None

    obj = event["data"]["object"]
    appt_id = (obj.get("metadata") or {}).get("appointment_id") or obj.get("client_reference_id")
    now_iso = timeutil.now_utc().isoformat()

    if event["type"] == "checkout.session.completed" and appt_id and obj.get("payment_status") == "paid":
        pi = obj.get("payment_intent")
        try:
            repo.confirm(appt_id, pi, now_iso)
            background.add_task(post_confirm, appt_id, repo, notifier, calendar)
        except ConfirmFailed:
            # Customer paid but the slot is gone (hold lapsed and someone else booked it,
            # or it was cancelled). Never keep money for a booking we can't honour.
            log.warning("late payment for %s - refunding", appt_id)
            if pi:
                payments.refund(pi)
        except NotFound:
            log.error("payment for unknown appointment %s", appt_id)

    elif event["type"] == "checkout.session.expired" and appt_id:
        appt = repo.get(appt_id)
        if appt and appt["status"] == "pending_payment":
            repo.cancel(appt_id, "system", now_iso)  # frees the slot immediately

    return {"received": True}
