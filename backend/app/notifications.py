"""Email (SES) and SMS (SNS). Failures are logged, never raised: a flaky notification must
not undo a booking."""

import logging

import boto3

from app.config import Settings
from app.timeutil import human_when

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, settings: Settings):
        self.s = settings
        self._ses = None
        self._sns = None

    @property
    def ses(self):
        self._ses = self._ses or boto3.client("ses", region_name=self.s.aws_region)
        return self._ses

    @property
    def sns(self):
        self._sns = self._sns or boto3.client("sns", region_name=self.s.aws_region)
        return self._sns

    def _email(self, to: str, subject: str, body: str) -> None:
        if not self.s.ses_from:
            log.info("email skipped (SES_FROM not set): %s -> %s", subject, to)
            return
        try:
            self.ses.send_email(
                Source=self.s.ses_from,
                Destination={"ToAddresses": [to]},
                Message={"Subject": {"Data": subject}, "Body": {"Text": {"Data": body}}},
            )
        except Exception:  # noqa: BLE001
            log.exception("email failed to %s", to)

    def _sms(self, phone: str, body: str) -> None:
        if not self.s.sms_enabled or not phone:
            return
        try:
            self.sns.publish(PhoneNumber=phone, Message=body[:300])
        except Exception:  # noqa: BLE001
            log.exception("sms failed")

    def send_confirmation(self, appt: dict) -> None:
        when = human_when(appt["date"], appt["time"])
        deposit = appt.get("deposit_cents", 0) / 100
        body = (
            f"Hi {appt['customer_name'] or 'there'},\n\n"
            f"You're booked at AfterHourzKutz.\n\n"
            f"Service: {appt['service_name']}\nWhen: {when}\n"
            f"Price: ${appt['price_cents'] / 100:.2f}"
            + (f" (deposit paid: ${deposit:.2f})" if appt.get("payment_intent_id") else "")
            + f"\n\nNeed to cancel? Do it at least {self.s.cancel_window_hours} hours ahead "
            f"to get your deposit back: {self.s.frontend_origin}/my-appointments\n\nSee you soon."
        )
        self._email(appt["customer_email"], "Your AfterHourzKutz appointment is confirmed", body)
        self._sms(appt.get("phone", ""), f"AfterHourzKutz: confirmed for {when}. See you then!")

    def send_cancellation(self, appt: dict, refunded: bool) -> None:
        when = human_when(appt["date"], appt["time"])
        note = "Your deposit has been refunded." if refunded else ""
        self._email(
            appt["customer_email"],
            "Your AfterHourzKutz appointment was cancelled",
            f"Your {appt['service_name']} on {when} was cancelled. {note}\n\n"
            f"Rebook anytime: {self.s.frontend_origin}/book",
        )
