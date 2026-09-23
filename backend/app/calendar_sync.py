"""One-way sync of confirmed bookings to the owner's Google Calendar.

Setup: create a service account, share your calendar with its email ("Make changes to
events"), and put the JSON key in the app secret as GOOGLE_SERVICE_ACCOUNT_JSON.
"""

import datetime as dt
import json
import logging

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import Settings
from app.timeutil import local_dt, tz_of

log = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


class CalendarSync:
    def __init__(self, settings: Settings):
        self.s = settings
        self._svc = None

    @property
    def enabled(self) -> bool:
        return bool(self.s.google_calendar_id and self.s.google_service_account_json)

    def _service(self):
        if self._svc is None:
            info = json.loads(self.s.google_service_account_json)
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            self._svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return self._svc

    def create_event(self, appt: dict) -> str | None:
        if not self.enabled:
            return None
        try:
            tz = tz_of(self.s.timezone)
            start = local_dt(appt["date"], appt["time"], tz)
            end = start + dt.timedelta(minutes=appt["duration_min"])
            body = {
                "summary": f"{appt['service_name']} - {appt['customer_name'] or appt['customer_email']}",
                "description": (
                    f"Client: {appt['customer_name']}\nEmail: {appt['customer_email']}\n"
                    f"Phone: {appt.get('phone', '')}\nNotes: {appt.get('notes', '')}\n"
                    f"Source: {appt.get('source', '')}"
                ),
                "start": {"dateTime": start.isoformat(), "timeZone": self.s.timezone},
                "end": {"dateTime": end.isoformat(), "timeZone": self.s.timezone},
            }
            event = self._service().events().insert(calendarId=self.s.google_calendar_id, body=body).execute()
            return event["id"]
        except Exception:  # noqa: BLE001
            log.exception("calendar create failed for %s", appt.get("id"))
            return None

    def delete_event(self, event_id: str | None) -> None:
        if not (self.enabled and event_id):
            return
        try:
            self._service().events().delete(calendarId=self.s.google_calendar_id, eventId=event_id).execute()
        except Exception:  # noqa: BLE001
            log.exception("calendar delete failed for %s", event_id)
