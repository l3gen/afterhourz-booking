import datetime as dt
from zoneinfo import ZoneInfo

from app.catalog import SLOT_MINUTES


def now_utc() -> dt.datetime:
    """Single seam for 'now' so tests can freeze time by monkeypatching this."""
    return dt.datetime.now(dt.UTC)


def tz_of(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def slots_for(start_hhmm: str, duration_min: int) -> list[str]:
    """Every SLOT_MINUTES block an appointment occupies, e.g. 10:00 + 60 -> [10:00, 10:30]."""
    start = to_min(start_hhmm)
    return [to_hhmm(start + i) for i in range(0, duration_min, SLOT_MINUTES)]


def local_dt(date_str: str, hhmm: str, tz: ZoneInfo) -> dt.datetime:
    d = dt.date.fromisoformat(date_str)
    m = to_min(hhmm)
    return dt.datetime(d.year, d.month, d.day, m // 60, m % 60, tzinfo=tz)


def human_when(date_str: str, hhmm: str) -> str:
    d = dt.date.fromisoformat(date_str)
    m = to_min(hhmm)
    t = dt.time(m // 60, m % 60)
    return f"{d.strftime('%A, %B')} {d.day} at {t.strftime('%I:%M %p').lstrip('0')}"
