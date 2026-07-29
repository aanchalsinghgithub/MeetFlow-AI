# MeetFlow AI – Google Calendar Auto-Join + Transcript Feature

This integrates: Google Calendar OAuth -> Upcoming Meetings Dashboard -> Auto Join -> Meeting Bot -> Audio Capture -> Transcription -> Speaker Detection -> Transcript Storage/Viewer, into the existing codebase with minimal, additive changes.

## 1. New files (backend)

- `app/services/audio_capture.py` – ffmpeg-based rolling WAV chunk recorder.
- `app/services/transcription_service.py` – wraps existing `SpeechToTextService` (faster-whisper), formats `[mm:ss]` timestamps, persists `Transcript` rows.
- `app/services/speaker_service.py` – wraps existing `DiarizationService` (pyannote.audio), assigns `Speaker 1`, `Speaker 2`, ... labels.
- `app/services/meeting_bot.py` – Playwright bot: joins Google Meet muted/cammed-off, captures audio, detects meeting end, updates `Meeting.status`.
- `app/services/scheduler_service.py` – APScheduler job (every 60s) that auto-launches the bot for meetings with `auto_join=True` due within 1 minute.
- `app/schemas/calendar.py` – Pydantic schemas for calendar connect/status, upcoming meetings, auto-join, transcript.
- `alembic/versions/0002_calendar_integration.py` – new tables/columns.

## 2. Modified files (backend)

- `app/core/config.py` – added `google_client_id`, `google_client_secret`, `google_redirect_uri`, `frontend_url`.
- `app/models/enums.py` – added `MeetingStatus` enum (`scheduled`, `bot_joining`, `in_progress`, `completed`, `failed`).
- `app/models/entities.py` – added `CalendarConnection`, `Transcript` models; added `status`, `auto_join`, `calendar_connection_id` to `Meeting` + relationships.
- `app/models/__init__.py` – exported new models.
- `app/services/calendar_service.py` – kept legacy `upcoming_meetings()`; added Google OAuth flow (`get_authorization_url`, `exchange_code`), token refresh, `sync_upcoming_meetings()` which fetches Google Meet events and upserts `Meeting`/`Participant` rows.
- `app/services/meeting_bot_service.py` – `join()` now launches `MeetingBot` in the background when a `meeting_id` is supplied.
- `app/api/routes/calendars.py` – added `GET /calendar/connect`, `GET /calendar/callback`, `GET /calendar/status`; kept legacy `/{provider}/upcoming`.
- `app/api/routes/meetings.py` – added `GET /meetings/upcoming`, `POST /meetings/{id}/auto-join`, `GET /meetings/{id}/status`, `GET /meetings/{id}/transcript`; `join-bot` now passes `meeting_id`.
- `app/api/router.py` – registered the calendars router under `/calendar`.
- `app/main.py` – starts/stops `SchedulerService` on app startup/shutdown.

## 3. New files (frontend)

- `src/components/MeetingsDashboard.tsx` – Upcoming Meetings dashboard: "Connect Google Calendar" button, meeting list with title/start time/duration/join URL/status/Auto Join toggle.
- `src/components/LiveTranscript.tsx` – Live Transcript viewer: auto-refresh (5s polling), speaker labels, timestamps, search box.

## 4. Modified files (frontend)

- `src/api.ts` – added `UpcomingMeeting`, `MeetingStatus`, `TranscriptEntry`, `TranscriptResponse`, `CalendarAuthURL`, `CalendarConnection` types.
- `src/App.tsx` – replaced the static "Meetings" page with `MeetingsDashboard`, replaced the sample "Live Meeting" transcript with `LiveTranscript` + a meeting selector, added a banner for the OAuth `?calendar=connected|error` redirect.

## 5. Database migration

Run from `backend/`:

```bash
cd backend
uv run alembic upgrade head
```

This creates `calendar_connections` and `transcripts` tables, and adds `status`, `auto_join`, `calendar_connection_id` columns to `meetings` (backward compatible, with server defaults so existing rows aren't broken).

## 6. New API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/calendar/connect` | Returns Google OAuth consent URL |
| GET | `/api/calendar/callback` | OAuth redirect target, stores tokens, redirects to frontend |
| GET | `/api/calendar/status` | Lists connected Google accounts |
| GET | `/api/meetings/upcoming` | Syncs + returns upcoming Google Meet meetings |
| POST | `/api/meetings/{id}/auto-join` | Body `{ "enabled": true|false }` – toggles Auto Join |
| GET | `/api/meetings/{id}/status` | Current bot/meeting status |
| GET | `/api/meetings/{id}/transcript` | Transcript entries, optional `?q=` search |

## 7. Environment variables (add to `.env`)

```env
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/calendar/callback
FRONTEND_URL=http://localhost:5173
```

In Google Cloud Console: enable the **Google Calendar API**, create an OAuth 2.0 Web client, and add `GOOGLE_REDIRECT_URI` as an authorized redirect URI.

## 8. New Python dependencies

> Note: this upload didn't include a `pyproject.toml`, so run these in your actual project root (where `pyproject.toml` lives):

```bash
uv add google-api-python-client google-auth google-auth-oauthlib
uv add apscheduler
uv add playwright
uv run playwright install chromium
uv add faster-whisper
uv add pyannote.audio
```

`faster-whisper` and `pyannote.audio` are already referenced (with try/except fallbacks) in `speech_service.py` / `diarization_service.py` — add them now if not already in `pyproject.toml`.

## 9. Deployment prerequisite: virtual audio device

The bot needs to "hear" the Google Meet tab's audio. On Linux:

```bash
pactl load-module module-null-sink sink_name=meetflow_bot
# Launch the backend with:
PULSE_SINK=meetflow_bot uv run uvicorn app.main:app --reload
```

`AudioCapture` reads from `meetflow_bot.monitor` by default (`input_device="default"` can be overridden per-bot if needed).

## 10. Running everything

```bash
# Backend
cd backend
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

Then in the UI: Meetings page -> "Connect Google Calendar" -> grant access -> upcoming Google Meet meetings appear -> toggle "Auto Join" -> at meeting start time the bot joins automatically, mutes mic/camera, captures audio, transcribes with speaker labels, and the Live Meeting page shows the transcript with auto-refresh and search.

## 11. Error handling implemented

- Expired Google tokens: refreshed automatically via `Credentials.refresh()`; sync failures are logged and skipped (don't crash the dashboard).
- Missing meeting URL: `/meetings/{id}/auto-join` returns `400` if `join_url` is empty; scheduler only picks meetings with a `join_url`.
- Bot join failure: `MeetingBot` catches exceptions, sets `status="failed"`, logs the error.
- Whisper/diarization failure: caught per-chunk, logged, returns empty/unlabeled segments rather than crashing the bot loop.
- Meeting ended: detected via Meet UI text or page closure; bot exits cleanly and sets `status="completed"`.
- Network errors (Calendar API): caught and logged in `sync_upcoming_meetings`, returns `[]` for that connection without affecting others.
