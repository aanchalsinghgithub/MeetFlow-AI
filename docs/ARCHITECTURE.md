# Architecture

MeetFlow AI separates provider integrations, AI services, workflow policy, and persistence.

## Core Components

- Calendar adapters detect upcoming Google Calendar and Outlook meetings.
- Meeting bot adapters join Google Meet, Microsoft Teams, and Zoom through approved organization accounts.
- Audio services run transcription and diarization with open-source defaults.
- Task extraction combines deterministic rules, Mistral JSON extraction, and correction feedback.
- Domain routing uses keywords first, embedding similarity next, and Mistral fallback.
- Approval workflow prevents direct developer assignment until a team lead approves, edits, or rejects.
- Notifications publish by email first, with Slack, Teams, and Jira adapters available.

## Data Flow

```text
meeting_detected -> bot_joined -> transcript_turns -> extracted_tasks
-> confidence_scored -> approval_requested -> task_assigned -> notifications_sent
```

## Extension Points

- Add platform-specific bot code in `backend/app/services/meeting_bot_service.py`.
- Add OAuth-backed calendar clients in `backend/app/services/calendar_service.py`.
- Add Jira implementation in `backend/app/services/notification_service.py`.
- Feed manager corrections into embeddings and future prompt examples through the `corrections` table.
