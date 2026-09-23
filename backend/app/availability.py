"""Pure functions that turn shop hours + existing bookings into bookable start times."""

import datetime as dt
from zoneinfo import ZoneInfo

from app.catalog import SLOT_MINUTES, Service
from app.timeutil import local_dt, slots_for, to_hhmm, to_min

# weekday() -> hours. 0 = Monday. Missing key = closed. Editable from the admin dashboard.
DEFAULT_HOURS: dict[str, dict[str, str]] = {
    str(d): {"open": "10:00", "close": "19:00"}
    for d in (1, 2, 3, 4, 5)  # Tue-Sat
}


def day_hours(config: dict, day: dt.date) -> dict | None:
    if day.isoformat() in config["closed_dates"]:
        return None
    return config["hours"].get(str(day.weekday()))


def open_days(config: dict, now_local: dt.datetime, max_days: int) -> list[str]:
    out = []
    for i in range(max_days + 1):
        d = now_local.date() + dt.timedelta(days=i)
        if day_hours(config, d):
            out.append(d.isoformat())
    return out


def available_times(
    config: dict,
    service: Service,
    day: dt.date,
    now_local: dt.datetime,
    taken: set[str],
    lead_minutes: int,
    max_days: int,
    tz: ZoneInfo,
) -> list[str]:
    if day < now_local.date() or day > now_local.date() + dt.timedelta(days=max_days):
        return []
    hours = day_hours(config, day)
    if not hours:
        return []
    earliest = now_local + dt.timedelta(minutes=lead_minutes)
    times = []
    last_start = to_min(hours["close"]) - service.duration_min
    for start in range(to_min(hours["open"]), last_start + 1, SLOT_MINUTES):
        hhmm = to_hhmm(start)
        if local_dt(day.isoformat(), hhmm, tz) < earliest:
            continue
        if any(s in taken for s in slots_for(hhmm, service.duration_min)):
            continue
        times.append(hhmm)
    return times


def validate_config(hours: dict, closed_dates: list[str]) -> None:
    """Raise ValueError on anything that would corrupt slot math."""
    for wd, h in hours.items():
        if wd not in {"0", "1", "2", "3", "4", "5", "6"}:
            raise ValueError(f"bad weekday key {wd!r}")
        o, c = to_min(h["open"]), to_min(h["close"])
        if o % SLOT_MINUTES or c % SLOT_MINUTES:
            raise ValueError(f"hours must be on {SLOT_MINUTES}-minute boundaries")
        if not 0 <= o < c <= 24 * 60:
            raise ValueError("open must be before close")
    for d in closed_dates:
        dt.date.fromisoformat(d)
