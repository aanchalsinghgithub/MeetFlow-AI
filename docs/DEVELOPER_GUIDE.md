# Developer Guide

## Python

Use UV only:

```powershell
uv venv
.venv\Scripts\activate
uv sync
uv add package-name
```

## Backend

```powershell
uv run uvicorn app.main:app --app-dir backend --reload
uv run pytest
uv run ruff check backend tests
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
npm run build
```

## API Workflow

Post transcript turns to:

```text
POST /api/meetings/process-transcript
```

The pipeline extracts tasks, classifies domains, computes confidence, creates manager approvals, and sends approval emails when SMTP is configured.
