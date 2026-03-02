# calendar_client.py
from __future__ import annotations

from typing import List, Dict, Optional, Iterable, Union
import os
import datetime as dt

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from google.oauth2.service_account import Credentials as ServiceAccountCredentials


DEFAULT_SCOPES = ["https://www.googleapis.com/auth/calendar"]
RFC3339 = str  # annotate for readability
DateOrDateTime = Union[dt.date, dt.datetime, RFC3339]


class GGCalendarAPI:
    """
    High-level Google Calendar API wrapper.

    Supports:
      - OAuth user consent (desktop/script) using credentials.json + token.json
      - Service Accounts (share the calendar with the SA email OR use domain-wide delegation with `subject`)

    Example (OAuth):
        client = GGCalendarAPI.oauth("credentials.json", token_path="token.json", default_calendar_id="primary")
        events = client.list_upcoming(max_results=5)

    Example (Service Account, shared to a Gmail calendar):
        sa = GGCalendarAPI.service_account(
            "service_account.json",
            default_calendar_id="yourgmail@gmail.com"  # your calendar must be shared to the SA with "Make changes"
        )
        sa.create_event(summary="Standup", start="2025-11-10T09:00:00", end="2025-11-10T09:15:00",
                        time_zone="Asia/Ho_Chi_Minh")

    Example (Service Account with Domain-wide Delegation):
        sa = GGCalendarAPI.service_account(
            "service_account.json",
            subject="user@your-domain.com",                # Workspace user to impersonate
            default_calendar_id="primary"                  # now refers to that user's primary
        )
    """

    # ---------- Construction ----------
    def __init__(
        self,
        credentials,
        api_version: str = "v3",
        default_calendar_id: Optional[str] = None
    ):
        self._creds = credentials
        self._service = build("calendar", api_version,
                              credentials=self._creds, cache_discovery=False)
        self.default_calendar_id = default_calendar_id

    @classmethod
    def oauth(
        cls,
        client_secrets_path: str,
        token_path: str = "token.json",
        scopes: Iterable[str] = DEFAULT_SCOPES,
        open_local_server: bool = True,
        default_calendar_id: Optional[str] = None,
    ) -> "GGCalendarAPI":
        """
        OAuth flow for local apps/scripts. Saves/refreshes token.json automatically.
        """
        creds: Optional[UserCredentials] = None
        if os.path.exists(token_path):
            creds = UserCredentials.from_authorized_user_file(
                token_path, scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and getattr(creds, "refresh_token", None):
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secrets_path, scopes)
                creds = flow.run_local_server(
                    port=0) if open_local_server else flow.run_console()
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

        return cls(creds, default_calendar_id=default_calendar_id)

    @classmethod
    def service_account(
        cls,
        service_account_key_path: str,
        scopes: Iterable[str] = DEFAULT_SCOPES,
        subject: Optional[str] = None,
        default_calendar_id: Optional[str] = None,
    ) -> "GGCalendarAPI":
        """
        Service Account for servers/cron. If using Workspace domain-wide delegation, pass `subject`
        (the user to impersonate). For personal Gmail calendars, share the calendar to the service
        account email and set default_calendar_id to that Gmail (or its calendar ID).
        """
        sa_creds = ServiceAccountCredentials.from_service_account_file(
            service_account_key_path, scopes=scopes)
        if subject:
            sa_creds = sa_creds.with_subject(subject)
        return cls(sa_creds, default_calendar_id=default_calendar_id)

    # ---------- Helpers ----------
    @staticmethod
    def _iso(dt_or_iso: DateOrDateTime) -> str:
        """
        Accepts ISO string or datetime/date object.
        - If datetime is naive, assume UTC.
        - If date is given, return date string (yyyy-mm-dd).
        """
        if isinstance(dt_or_iso, dt.datetime):
            if dt_or_iso.tzinfo is None:
                dt_or_iso = dt_or_iso.replace(tzinfo=dt.timezone.utc)
            return dt_or_iso.isoformat()
        if isinstance(dt_or_iso, dt.date):
            return dt_or_iso.isoformat()
        return dt_or_iso

    def _resolve_calendar_id(self, calendar_id: Optional[str]) -> str:
        cal_id = calendar_id or self.default_calendar_id or "primary"
        return cal_id

    def who_am_i(self) -> str:
        """
        Returns the active identity: service account email (if SA) or the first visible calendar id (OAuth).
        """
        sa_email = getattr(self._creds, "service_account_email", None)
        if sa_email:
            return f"Service Account: {sa_email}"
        try:
            cal_list = self._service.calendarList().list(maxResults=1).execute()
            items = cal_list.get("items", [])
            if items:
                return f"OAuth user calendar id: {items[0].get('id')}"
        except Exception:
            pass
        return "Unknown identity"

    # ---------- Calendars ----------
    def list_calendars(self) -> List[Dict]:
        resp = self._service.calendarList().list().execute()
        return resp.get("items", [])

    def create_calendar(self, summary: str, time_zone: str = "Asia/Ho_Chi_Minh") -> Dict:
        body = {"summary": summary, "timeZone": time_zone}
        return self._service.calendars().insert(body=body).execute()

    # ---------- Events ----------
    def list_upcoming(
        self,
        calendar_id: Optional[str] = None,
        max_results: int = 10,
        time_min: Optional[DateOrDateTime] = None,
    ) -> List[Dict]:
        cal_id = self._resolve_calendar_id(calendar_id)
        if time_min is None:
            time_min = dt.datetime.utcnow().isoformat() + "Z"
        else:
            time_min = self._iso(time_min)

        resp = self._service.events().list(
            calendarId=cal_id,
            timeMin=time_min,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return resp.get("items", [])

    def get_event(self, event_id: str, calendar_id: Optional[str] = None) -> Dict:
        cal_id = self._resolve_calendar_id(calendar_id)
        return self._service.events().get(calendarId=cal_id, eventId=event_id).execute()

    def create_event(
        self,
        summary: str,
        start: DateOrDateTime,
        end: DateOrDateTime,
        time_zone: str = "Asia/Ho_Chi_Minh",
        calendar_id: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        reminders_minutes: Optional[int] = 10,
        recurrence_rrule: Optional[str] = None,
        send_updates: str = "all",
    ) -> Dict:
        cal_id = self._resolve_calendar_id(calendar_id)
        body: Dict = {
            "summary": summary,
            "start": {"dateTime": self._iso(start), "timeZone": time_zone},
            "end": {"dateTime": self._iso(end), "timeZone": time_zone},
        }
        if location:
            body["location"] = location
        if description:
            body["description"] = description
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]
        if reminders_minutes is not None:
            body["reminders"] = {"useDefault": False, "overrides": [
                {"method": "popup", "minutes": reminders_minutes},
                {"method": "email", "minutes": reminders_minutes}
            ]}
        if recurrence_rrule:
            body["recurrence"] = [recurrence_rrule]

        # Debug: In ra body để kiểm tra
        import json
        print("📤 Request body being sent to Google Calendar API:")
        print(json.dumps(body, indent=2, ensure_ascii=False))

        result = self._service.events().insert(calendarId=cal_id, body=body,
                                               sendUpdates=send_updates).execute()

        # Debug: In ra response để kiểm tra
        print("📥 Response from Google Calendar API:")
        print(json.dumps(result.get("reminders", {}), indent=2, ensure_ascii=False))

        return result

    def create_all_day_event(
        self,
        summary: str,
        date: Union[dt.date, RFC3339],
        calendar_id: Optional[str] = None,
        description: Optional[str] = None,
        send_updates: str = "all",
    ) -> Dict:
        """
        All-day event: end date is exclusive (date + 1 day).
        """
        if isinstance(date, str):
            d0 = dt.date.fromisoformat(date)
        else:
            d0 = date
        d1 = d0 + dt.timedelta(days=1)
        cal_id = self._resolve_calendar_id(calendar_id)
        body: Dict = {
            "summary": summary,
            "start": {"date": d0.isoformat()},
            "end": {"date": d1.isoformat()},
        }
        if description:
            body["description"] = description
        return self._service.events().insert(calendarId=cal_id, body=body, sendUpdates=send_updates).execute()

    def update_event(self, event_id: str, calendar_id: Optional[str] = None, **fields) -> Dict:
        """
        Update arbitrary fields of an event. Example:
            update_event(id, summary="New title", description="...")
        For nested fields, pass full structures, e.g.:
            start={"dateTime": "...", "timeZone": "..."}
        """
        cal_id = self._resolve_calendar_id(calendar_id)
        current = self.get_event(event_id, cal_id)
        current.update(fields)
        return self._service.events().update(calendarId=cal_id, eventId=event_id, body=current).execute()

    def delete_event(self, event_id: str, calendar_id: Optional[str] = None, send_updates: str = "all") -> None:
        cal_id = self._resolve_calendar_id(calendar_id)
        self._service.events().delete(calendarId=cal_id, eventId=event_id,
                                      sendUpdates=send_updates).execute()

    # ---------- Watches (push notifications) ----------
    def watch_events(self, callback_url: str, calendar_id: Optional[str] = None, ttl_seconds: int = 3600) -> Dict:
        """
        Start a push notification channel. You must expose `callback_url` (HTTPS) and handle X-Goog headers.
        Note: Channels expire; you need to renew.
        """
        import uuid
        channel_id = str(uuid.uuid4())
        cal_id = self._resolve_calendar_id(calendar_id)
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": callback_url,
            "params": {"ttl": str(ttl_seconds)},
        }
        return self._service.events().watch(calendarId=cal_id, body=body).execute()

    def stop_channel(self, channel_id: str, resource_id: str) -> None:
        self._service.channels().stop(
            body={"id": channel_id, "resourceId": resource_id}).execute()


# ---------- Quick self-test & examples ----------
if __name__ == "__main__":
    """
    Pick ONE of the blocks below and comment the other out.
    """

    # ===== Service Account to a Gmail calendar you shared to the SA =====
    # 1) Share your calendar (calendar.google.com) to the SA email with "Make changes to events".
    # 2) Set default_calendar_id to *your* Gmail (or that calendar's ID).
