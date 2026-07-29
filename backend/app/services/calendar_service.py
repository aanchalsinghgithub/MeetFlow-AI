"""Google Calendar integration: OAuth flow, token refresh, and meeting sync.

Extends the original lightweight CalendarIntegrationService stub. The legacy
``upcoming_meetings`` method is preserved for any existing callers / demo use,
while the new methods implement the real Google OAuth + Calendar API flow
used by the Upcoming Meetings dashboard and Auto Join workflow.
"""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import logging
import secrets

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import CalendarConnection, Meeting, Participant
from app.models.enums import MeetingProvider, MeetingStatus

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

GOOGLE_MEET_MARKER = "meet.google.com"

# In-memory store for PKCE and tenant context between connect and callback.
_pkce_store: dict[str, dict[str, int | str]] = {}


def _generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    code_verifier = secrets.token_urlsafe(96)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


class CalendarIntegrationService:
    """Legacy + Google Calendar integration."""

    # ------------------------------------------------------------------
    # Legacy / demo behaviour (kept for backward compatibility)
    # ------------------------------------------------------------------
    def upcoming_meetings(self, provider: str, since: datetime) -> list[dict]:
        return [
            {
                "provider": provider,
                "title": "Product sync",
                "starts_at": since.isoformat(),
                "join_url": "https://meet.example.com/demo",
            }
        ]

    # ------------------------------------------------------------------
    # OAuth flow
    # ------------------------------------------------------------------
    def _build_flow(self, state: str | None = None):
        from google_auth_oauthlib.flow import Flow

        if not settings.google_client_id or not settings.google_client_secret:
            raise RuntimeError(
                "Google Calendar is not configured. Set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET environment variables."
            )

        client_config = {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        }
        return Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            state=state,
            redirect_uri=settings.google_redirect_uri,
        )

    def get_authorization_url(self, user_id: int, organization_id: int) -> str:
        """Return the Google OAuth consent screen URL (with PKCE S256)."""
        flow = self._build_flow()
        code_verifier, code_challenge = _generate_pkce_pair()
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )
        _pkce_store[state] = {
            "code_verifier": code_verifier,
            "user_id": user_id,
            "organization_id": organization_id,
        }
        return authorization_url

    def exchange_code(self, code: str, state: str, db: Session) -> CalendarConnection:
        """Exchange an OAuth authorization code for tokens and persist them."""
        state_payload = _pkce_store.pop(state, None)
        if not state_payload:
            raise RuntimeError("OAuth state expired or invalid. Please reconnect Google Calendar.")

        organization_id = int(state_payload["organization_id"])
        code_verifier = state_payload.get("code_verifier")
        flow = self._build_flow(state=state)
        fetch_kwargs: dict = {"code": code}
        if code_verifier:
            fetch_kwargs["code_verifier"] = code_verifier
        flow.fetch_token(**fetch_kwargs)
        credentials = flow.credentials

        user_email = self._fetch_user_email(credentials)

        connection = (
            db.query(CalendarConnection)
            .filter(
                CalendarConnection.organization_id == organization_id,
                CalendarConnection.user_email == user_email,
            )
            .one_or_none()
        )
        # google-auth's Credentials.expiry / .expired property expects a naive
        # UTC datetime. Forcing tzinfo onto it here made every subsequent
        # `credentials.expired` check raise "can't compare offset-naive and
        # offset-aware datetimes", which was swallowed by the broad
        # try/except in sync_upcoming_meetings() — so calendar sync silently
        # failed every time a connection needed its token checked/refreshed.
        token_expiry = credentials.expiry
        if token_expiry and token_expiry.tzinfo is not None:
            token_expiry = token_expiry.astimezone(timezone.utc).replace(tzinfo=None)

        if connection is None:
            connection = CalendarConnection(
                organization_id=organization_id,
                user_email=user_email,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expiry=token_expiry,
            )
            db.add(connection)
        else:
            connection.organization_id = organization_id
            connection.access_token = credentials.token
            if credentials.refresh_token:
                connection.refresh_token = credentials.refresh_token
            connection.token_expiry = token_expiry

        db.commit()
        db.refresh(connection)
        return connection

    @staticmethod
    def _fetch_user_email(credentials) -> str:
        from googleapiclient.discovery import build

        oauth2_service = build("oauth2", "v2", credentials=credentials)
        userinfo = oauth2_service.userinfo().get().execute()
        email = userinfo.get("email")
        if not email:
            raise RuntimeError("Could not determine Google account email")
        return email

    # ------------------------------------------------------------------
    # Credential refresh
    # ------------------------------------------------------------------
    def _credentials_for(self, connection: CalendarConnection, db: Session):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        credentials = Credentials(
            token=connection.access_token,
            refresh_token=connection.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=SCOPES,
        )

        if connection.token_expiry:
            credentials.expiry = connection.token_expiry

        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            connection.access_token = credentials.token
            connection.token_expiry = credentials.expiry
            db.commit()

        return credentials

    # ------------------------------------------------------------------
    # Fetch + sync upcoming meetings
    # ------------------------------------------------------------------
    def sync_upcoming_meetings(self, db: Session, connection: CalendarConnection, max_results: int = 25) -> list[Meeting]:
        """Fetch upcoming Google Meet events for a connection and upsert them."""
        from googleapiclient.discovery import build

        try:
            credentials = self._credentials_for(connection, db)
            service = build("calendar", "v3", credentials=credentials)

            now = datetime.now(timezone.utc).isoformat()
            time_max = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()

            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=now,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
        except Exception:
            logger.exception("Failed to fetch Google Calendar events for %s", connection.user_email)
            return []

        synced: list[Meeting] = []
        for event in events:
            join_url = self._extract_meet_url(event)
            if not join_url:
                continue

            meeting = self._upsert_meeting(db, connection, event, join_url)
            synced.append(meeting)

        db.commit()
        return synced

    @staticmethod
    def _extract_meet_url(event: dict) -> str | None:
        conference_data = event.get("conferenceData", {})
        for entry_point in conference_data.get("entryPoints", []):
            uri = entry_point.get("uri", "")
            if GOOGLE_MEET_MARKER in uri:
                return uri

        for field in ("hangoutLink", "location"):
            value = event.get(field, "") or ""
            if GOOGLE_MEET_MARKER in value:
                return value

        description = event.get("description", "") or ""
        if GOOGLE_MEET_MARKER in description:
            for token in description.split():
                if GOOGLE_MEET_MARKER in token:
                    return token.strip("<>,.")

        return None

    @staticmethod
    def _parse_event_time(value: dict) -> datetime | None:
        raw = value.get("dateTime") or value.get("date")
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        # Normalize to naive UTC so this matches datetime.utcnow() comparisons
        # used everywhere else in the app (routes, scheduler) and stores
        # cleanly in SQLite's DateTime column.
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    def _upsert_meeting(self, db: Session, connection: CalendarConnection, event: dict, join_url: str) -> Meeting:
        external_id = event.get("id")
        meeting = (
            db.query(Meeting)
            .filter(
                Meeting.organization_id == connection.organization_id,
                Meeting.external_id == external_id,
                Meeting.provider == MeetingProvider.GOOGLE_MEET.value,
            )
            .one_or_none()
        )

        starts_at = self._parse_event_time(event.get("start", {}))
        ends_at = self._parse_event_time(event.get("end", {}))
        title = event.get("summary") or "Untitled meeting"

        if meeting is None:
            meeting = Meeting(
                organization_id=connection.organization_id,
                title=title,
                provider=MeetingProvider.GOOGLE_MEET.value,
                external_id=external_id,
                join_url=join_url,
                starts_at=starts_at,
                ends_at=ends_at,
                status=MeetingStatus.SCHEDULED.value,
                calendar_connection_id=connection.id,
            )
            db.add(meeting)
            db.flush()
        else:
            meeting.organization_id = connection.organization_id
            meeting.title = title
            meeting.join_url = join_url
            meeting.starts_at = starts_at
            meeting.ends_at = ends_at
            meeting.calendar_connection_id = connection.id

        self._sync_participants(db, meeting, event)
        return meeting

    @staticmethod
    def _sync_participants(db: Session, meeting: Meeting, event: dict) -> None:
        existing = {participant.email for participant in meeting.participants if participant.email}
        for attendee in event.get("attendees", []):
            email = attendee.get("email")
            if not email or email in existing:
                continue
            db.add(Participant(meeting_id=meeting.id, name=attendee.get("displayName", email), email=email))
            existing.add(email)
