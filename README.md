# MeetFlow AI

**Meetings -> Workflows Automatically**

MeetFlow AI is a SaaS platform scaffold for autonomous meeting intelligence: calendar detection, bot meeting capture, transcription, speaker-aware task extraction, domain routing, manager approval, and task notifications.

## Quick Start

### Backend

```powershell
uv venv
.venv\Scripts\activate
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --app-dir backend --reload
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

### Docker

```powershell
docker compose up --build
```

## Architecture

```text
Calendar Integrations
        |
Meeting Bot Connectors
        |
Audio Capture -> STT -> Diarization
        |
Meeting Understanding
        |
Task Extraction -> Domain Classification -> Confidence Scoring
        |
Approval Workflow
        |
Email / Slack / Teams / Jira Notifications
        |
Dashboard and Analytics
```

Backend layout follows clean architecture:

```text
backend/app/api          HTTP route modules
backend/app/core         settings, security, logging, database
backend/app/models       SQLAlchemy ORM models
backend/app/repositories persistence access
backend/app/schemas      Pydantic contracts
backend/app/services     business and AI services
backend/app/workers      Celery jobs
```

## Environment

Copy `.env.example` to `.env` and set secrets.

Required for AI extraction:

```text
MISTRAL_API_KEY=
```

Optional local/open-source components are wired as service boundaries:

- `faster-whisper` for speech to text
- `pyannote.audio` for speaker diarization
- `sentence-transformers` using `all-MiniLM-L6-v2`
- ChromaDB for vector search
- Tesseract for OCR

## Main Features

- JWT authentication and role-based access control
- Meeting metadata and participant tracking
- Speaker-aware task extraction
- Hybrid domain classification: keywords, embeddings, Mistral fallback
- Confidence scoring with approval thresholds
- Manager approval queue: approve, edit, reject
- Email workflows for summaries, approvals, and assignments
- Slack, Microsoft Teams, and Jira notifier extension points
- Dashboard pages for meetings, live view, tasks, approvals, analytics, and settings

## API Docs

Run the backend and open:

- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Testing

```powershell
uv run pytest
```

## Production Notes

The meeting auto-join connectors are intentionally adapter-based. Production deployment should use approved bot accounts, organization consent, and the platform APIs for Google Meet, Microsoft Teams, and Zoom. Recording and transcription features must comply with local consent laws and enterprise policy.
