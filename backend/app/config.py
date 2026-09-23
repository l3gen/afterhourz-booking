"""Application settings, read from environment variables (12-factor).

In AWS these come from the ECS task definition: plain values as environment
variables, sensitive values injected from a single Secrets Manager secret.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_JWT_SECRET = "dev-only-change-me"  # noqa: S105 - sentinel, rejected outside local


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- runtime -----------------------------------------------------------
    env: str = "local"  # local | dev | prod
    aws_region: str = "us-east-1"
    table_name: str = "afterhourz-local"
    dynamodb_endpoint_url: str | None = None  # set for DynamoDB Local
    timezone: str = "America/New_York"
    frontend_origin: str = "http://localhost:5173"
    cors_origins: str = ""  # comma separated; only needed for local dev

    # --- auth --------------------------------------------------------------
    google_client_id: str = ""
    admin_emails: str = ""  # comma separated Google accounts allowed into /admin
    jwt_secret: str = INSECURE_DEFAULT_JWT_SECRET
    jwt_ttl_hours: int = 12
    dev_login_enabled: bool = False  # local development only, refused elsewhere

    # --- booking rules -----------------------------------------------------
    lead_time_minutes: int = 120
    max_advance_days: int = 30
    cancel_window_hours: int = 24  # deposit refundable if cancelled this far ahead

    # --- payments (Stripe) -------------------------------------------------
    payments_enabled: bool = False
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # --- integrations ------------------------------------------------------
    google_calendar_id: str = ""
    google_service_account_json: str = ""
    ses_from: str = ""  # verified SES sender, e.g. bookings@yourdomain.com
    sms_enabled: bool = False

    @model_validator(mode="after")
    def _refuse_insecure_config(self) -> "Settings":
        if self.env != "local":
            if self.jwt_secret == INSECURE_DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a random 32+ char value outside local")
            if self.dev_login_enabled:
                raise ValueError("DEV_LOGIN_ENABLED is only allowed when ENV=local")
        if self.payments_enabled and not (self.stripe_secret_key and self.stripe_webhook_secret):
            raise ValueError("PAYMENTS_ENABLED requires STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET")
        return self

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def allowed_origins(self) -> list[str]:
        extra = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return [self.frontend_origin, *extra]


@lru_cache
def get_settings() -> Settings:
    return Settings()
