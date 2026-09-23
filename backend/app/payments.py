"""Stripe deposits via hosted Checkout (card data never touches our servers)."""

import logging

import stripe

from app.config import Settings

log = logging.getLogger(__name__)

# Stripe requires Checkout Sessions to live at least 30 minutes. We hold the slot slightly
# longer than the session so a payment completed at the last second still confirms.
HOLD_SECONDS = 31 * 60


class Payments:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.settings.payments_enabled

    def create_checkout(self, appt: dict, now_epoch: int) -> tuple[str, str]:
        s = self.settings
        session = stripe.checkout.Session.create(
            api_key=s.stripe_secret_key,
            mode="payment",
            client_reference_id=appt["id"],
            customer_email=appt["customer_email"],
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": appt["deposit_cents"],
                        "product_data": {"name": f"Deposit - {appt['service_name']}"},
                    },
                }
            ],
            metadata={"appointment_id": appt["id"]},
            expires_at=now_epoch + 30 * 60 + 30,
            success_url=f"{s.frontend_origin}/booking/success?appt={appt['id']}",
            cancel_url=f"{s.frontend_origin}/book?payment=cancelled&appt={appt['id']}",
        )
        return session["id"], session["url"]

    def refund(self, payment_intent_id: str) -> None:
        stripe.Refund.create(api_key=self.settings.stripe_secret_key, payment_intent=payment_intent_id)

    def parse_event(self, payload: bytes, signature: str):
        """Verifies the Stripe signature. Raises ValueError / stripe.SignatureVerificationError."""
        return stripe.Webhook.construct_event(payload, signature, self.settings.stripe_webhook_secret)
