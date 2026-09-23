import datetime as dt
import re

from pydantic import BaseModel, Field, field_validator

PHONE_RE = re.compile(r"^\+?[0-9 ()\-.]{7,20}$")
HHMM_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def normalize_phone(raw: str) -> str:
    """Best-effort E.164 for US numbers (what SNS needs). Non-US numbers must include +."""
    digits = re.sub(r"\D", "", raw)
    if raw.strip().startswith("+"):
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return "+" + digits


class GoogleLogin(BaseModel):
    credential: str = Field(min_length=10, max_length=4096)


class DevLogin(BaseModel):
    email: str
    name: str = "Dev User"


class AppointmentCreate(BaseModel):
    service_id: str = Field(max_length=40)
    date: dt.date
    time: str
    phone: str
    notes: str = Field(default="", max_length=500)
    source: str = Field(default="direct", max_length=80)  # e.g. google-business-profile

    @field_validator("time")
    @classmethod
    def _time(cls, v: str) -> str:
        if not HHMM_RE.match(v):
            raise ValueError("time must be HH:MM")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        if not PHONE_RE.match(v.strip()):
            raise ValueError("enter a valid phone number")
        return normalize_phone(v)

    @field_validator("source")
    @classmethod
    def _source(cls, v: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_.\-]", "", v)[:80] or "direct"


class ConfigUpdate(BaseModel):
    hours: dict[str, dict[str, str]]  # {"1": {"open": "10:00", "close": "19:00"}, ...}
    closed_dates: list[str] = []
