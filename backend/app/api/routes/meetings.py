from datetime import datetime
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.entities import CalendarConnection, Meeting, Participant, Transcript
from app.schemas.calendar import (
    AutoJoinUpdate,
    MeetingStatusRead,
    TranscriptEntryRead,
    TranscriptResponse,
    UpcomingMeetingRead,
)
from app.schemas.meeting import (
    MeetingCreate,
    MeetingDetail,
    MeetingRead,
    MeetingSummaryUpdate,
    ProcessTranscriptRequest,
    ProcessTranscriptResponse,
    SendSummaryRequest,
    SendSummaryResponse,
)
from app.services.calendar_service import CalendarIntegrationService
from app.services.email_service import EmailService
from app.services.meeting_bot_service import MeetingBotService
from app.services.meeting_pipeline import MeetingPipeline
from app.services.transcription_service import TranscriptionService

from app.models.enums import MeetingStatus
from app.schemas.meeting import TranscriptTurn

router = APIRouter()


def _get_org_meeting(db: Session, meeting_id: int, organization_id: int) -> Meeting | None:
    return (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id, Meeting.organization_id == organization_id)
        .one_or_none()
    )


@router.post("", response_model=MeetingRead)
def create_meeting(
    payload: MeetingCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Meeting:
    meeting = Meeting(
        organization_id=current_user.organization_id,
        title=payload.title,
        provider=payload.provider.value,
        external_id=payload.external_id,
        join_url=payload.join_url,
        starts_at=payload.starts_at,
    )
    db.add(meeting)
    db.flush()
    for participant in payload.participants:
        db.add(Participant(meeting_id=meeting.id, name=participant, email=participant if "@" in participant else None))
    db.commit()
    db.refresh(meeting)
    return meeting


@router.get("", response_model=list[MeetingRead])
def list_meetings(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[Meeting]:
    return (
        db.query(Meeting)
        .filter(Meeting.organization_id == current_user.organization_id)
        .order_by(Meeting.created_at.desc())
        .all()
    )


@router.get("/upcoming", response_model=list[UpcomingMeetingRead])
def upcoming_meetings(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Upcoming Meetings Dashboard data source.

    Refreshes meetings from any connected Google Calendar accounts, then
    returns Google Meet meetings starting from now onward, ordered by start
    time, with Auto Join state and current bot status.
    """
    calendar_service = CalendarIntegrationService()
    for connection in (
        db.query(CalendarConnection)
        .filter(CalendarConnection.organization_id == current_user.organization_id)
        .all()
    ):
        calendar_service.sync_upcoming_meetings(db, connection)

    now = datetime.utcnow()
    meetings = (
        db.query(Meeting)
        .filter(Meeting.organization_id == current_user.organization_id)
        .filter(Meeting.join_url.isnot(None))
        .filter((Meeting.ends_at.is_(None)) | (Meeting.ends_at >= now))
        .order_by(Meeting.starts_at.asc())
        .all()
    )

    return [
        {
            "id": meeting.id,
            "title": meeting.title,
            "provider": meeting.provider,
            "join_url": meeting.join_url,
            "starts_at": meeting.starts_at,
            "ends_at": meeting.ends_at,
            "status": meeting.status,
            "auto_join": meeting.auto_join,
            "participants": [p.name for p in meeting.participants],
        }
        for meeting in meetings
    ]


@router.get("/recent", response_model=list[UpcomingMeetingRead])
def recent_meetings(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    limit: int = 20,
) -> list[dict]:
    """Meeting history for the sidebar's "Recent" tab.

    BUGFIX: /upcoming filters out anything whose ends_at has passed, which
    is correct for "what should I join next" but means a meeting silently
    disappears from the only list the UI has as soon as it's over — so
    there was no way to click back into a *completed* meeting to see its
    transcript/summary once its scheduled end time passed. This endpoint
    has no such filter, just the most recent N meetings regardless of
    status.
    """
    meetings = (
        db.query(Meeting)
        .filter(Meeting.organization_id == current_user.organization_id)
        .order_by(Meeting.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": meeting.id,
            "title": meeting.title,
            "provider": meeting.provider,
            "join_url": meeting.join_url,
            "starts_at": meeting.starts_at,
            "ends_at": meeting.ends_at,
            "status": meeting.status,
            "auto_join": meeting.auto_join,
            "participants": [p.name for p in meeting.participants],
        }
        for meeting in meetings
    ]


def _meeting_detail_dict(meeting: Meeting) -> dict:
    return {
        "id": meeting.id,
        "title": meeting.title,
        "provider": meeting.provider,
        "join_url": meeting.join_url,
        "starts_at": meeting.starts_at,
        "ends_at": meeting.ends_at,
        "summary": meeting.summary,
        "decisions": meeting.decisions,
        "key_discussion_points": meeting.key_discussion_points,
        "risks": meeting.risks,
        "blockers": meeting.blockers,
        "transcript": meeting.transcript,
        "participants": [participant.name for participant in meeting.participants],
        "participant_emails": [participant.email for participant in meeting.participants if participant.email],
        "task_count": len(meeting.tasks),
    }


@router.get("/{meeting_id}", response_model=MeetingDetail)
def get_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    meeting = _get_org_meeting(db, meeting_id, current_user.organization_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return _meeting_detail_dict(meeting)


# ------------------------------------------------------------------
# NEW: edit the AI-generated summary (and delete/add individual discussion
# points, decisions, risks, blockers) from the Approval Queue's summary
# panel. Partial update - exclude_unset means a field that wasn't sent in
# the request body is left untouched, so the frontend can save just the
# section the user actually edited.
# ------------------------------------------------------------------
@router.patch("/{meeting_id}/summary", response_model=MeetingDetail)
def update_meeting_summary(
    meeting_id: int,
    payload: MeetingSummaryUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    meeting = _get_org_meeting(db, meeting_id, current_user.organization_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    updates = payload.model_dump(exclude_unset=True)
    if "summary" in updates:
        meeting.summary = updates["summary"]
    if "key_discussion_points" in updates:
        meeting.key_discussion_points = updates["key_discussion_points"]
    if "decisions" in updates:
        meeting.decisions = updates["decisions"]
    if "risks" in updates:
        meeting.risks = updates["risks"]
    if "blockers" in updates:
        meeting.blockers = updates["blockers"]

    db.commit()
    db.refresh(meeting)
    return _meeting_detail_dict(meeting)


# ------------------------------------------------------------------
# NEW: manual meeting-summary send, callable from the Approval Queue's
# meeting-summary panel. Two things this covers that the automatic send in
# MeetingPipeline.process_transcript() can't:
#   1. Adding a recipient who wasn't an original meeting participant.
#   2. Sending (or re-sending) whenever the user chooses - e.g. after
#      reviewing/approving the tasks from that meeting - rather than only
#      once, automatically, at finalize time.
# ------------------------------------------------------------------
@router.post("/{meeting_id}/send-summary", response_model=SendSummaryResponse)
def send_meeting_summary(
    meeting_id: int,
    payload: SendSummaryRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    meeting = _get_org_meeting(db, meeting_id, current_user.organization_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Explicit recipients from the UI win; otherwise fall back to whichever
    # participants have a real email on file.
    recipients = [r.strip() for r in payload.recipients if r.strip()]
    if not recipients:
        recipients = [p.email for p in meeting.participants if p.email]
    if not recipients:
        raise HTTPException(
            status_code=400,
            detail="No recipients to send to - add at least one email address.",
        )

    email = EmailService()
    results = []
    for recipient in recipients:
        try:
            sent = email.meeting_summary(recipient, meeting)
            results.append({"recipient": recipient, "sent": sent, "error": None if sent else "Send failed - check SMTP settings."})
        except Exception as e:  # pragma: no cover - defensive, meeting_summary() doesn't normally raise
            results.append({"recipient": recipient, "sent": False, "error": str(e)})

    return {"results": results}


@router.post("/process-transcript", response_model=ProcessTranscriptResponse)
async def process_transcript(
    payload: ProcessTranscriptRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ProcessTranscriptResponse:
    return await MeetingPipeline(db, current_user.organization_id).process_transcript(payload)


# ------------------------------------------------------------------
# NEW: Electron WASAPI audio chunk ingestion
# ------------------------------------------------------------------
@router.post("/{meeting_id}/audio")
async def upload_audio_chunk(
    meeting_id: int,
    audio: UploadFile = File(...),
    chunk_offset: float = 0.0,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Accept a WAV audio chunk from the Electron desktop app.

    The Electron app captures system audio via Windows WASAPI Loopback,
    splits it into 15-second WAV chunks, and POSTs them here.
    Each chunk is transcribed immediately and stored in the DB.

    Args:
        meeting_id: Target meeting ID.
        audio:        Uploaded WAV file (multipart/form-data field ``audio``).
        chunk_offset: Start time offset in seconds for this chunk within the
                      meeting (used to compute absolute timestamps).
    """
    meeting = _get_org_meeting(db, meeting_id, current_user.organization_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting.status not in ("in_progress", "bot_joining"):
        raise HTTPException(
            status_code=400,
            detail=f"Meeting is not active (status={meeting.status}). Start the bot first.",
        )

    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file received.")

    # Write to a named temp file so TranscriptionService can open it by path
    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        prefix=f"meetflow_{meeting_id}_chunk_",
        delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        transcription = TranscriptionService()
        entries: list[Transcript] = transcription.process_chunk_and_store(
            db, meeting_id, tmp_path, chunk_offset_seconds=chunk_offset
        )
        return {
            "status": "ok",
            "meeting_id": meeting_id,
            "chunk_offset": chunk_offset,
            "filename": audio.filename,
            "bytes_received": len(content),
            "segments_stored": len(entries),
            "transcript": [
                {
                    "speaker": e.speaker,
                    "text": e.text,
                    "timestamp": e.timestamp,
                }
                for e in entries
            ],
        }
    finally:
        tmp_path.unlink(missing_ok=True)


# -----------------------------------------------------

@router.post("/{meeting_id}/finalize", response_model=ProcessTranscriptResponse)
async def finalize_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ProcessTranscriptResponse:
    meeting = _get_org_meeting(db, meeting_id, current_user.organization_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    entries = (
        db.query(Transcript)
        .filter(Transcript.meeting_id == meeting_id)
        .order_by(Transcript.id.asc())
        .all()
    )
    if not entries:
        raise HTTPException(status_code=400, detail="No transcript captured yet")

    payload = ProcessTranscriptRequest(
        meeting_id=meeting.id,
        meeting_title=meeting.title,
        participants=[p.name for p in meeting.participants],
        transcript=[
            TranscriptTurn(speaker=e.speaker, text=e.text, timestamp=e.timestamp)
            for e in entries
        ],
    )
    result = await MeetingPipeline(db, current_user.organization_id).process_transcript(payload)
    meeting.status = MeetingStatus.COMPLETED.value
    db.commit()
    return result


# ------------------------------------------------------------------
# Existing endpoints (unchanged)
# ------------------------------------------------------------------
@router.post("/{meeting_id}/join-bot")
def join_bot(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    print("\n===================================")
    print("JOIN BOT ENDPOINT HIT")
    print(f"Meeting ID = {meeting_id}")
    print("===================================\n")

    meeting = _get_org_meeting(db, meeting_id, current_user.organization_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    result = MeetingBotService().join(
        meeting.provider,
        meeting.join_url or "",
        meeting_id=meeting.id,
    )

    print(f"JOIN RESULT => {result}")
    return result


@router.post("/{meeting_id}/test-transcript")
def inject_test_transcript(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """DEV ONLY: Inject sample transcript entries to test the Live Transcript UI."""
    meeting = _get_org_meeting(db, meeting_id, current_user.organization_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting.status = "in_progress"
    sample = [
        ("Speaker 1", "Hello, this is a test meeting for MeetFlow AI.", "00:00"),
        ("Speaker 2", "Yes, I am testing the automatic transcription feature.", "00:05"),
        ("Speaker 1", "The bot should be capturing audio and converting it to text.", "00:12"),
        ("Speaker 2", "Let's assign the login redesign task to Ajay by next Friday.", "00:20"),
        ("Speaker 1", "Agreed. Priya will fix the API timeout issue this sprint.", "00:28"),
    ]
    for speaker, text, timestamp in sample:
        db.add(Transcript(meeting_id=meeting_id, speaker=speaker, text=text, timestamp=timestamp))
    db.commit()
    return {"status": "ok", "entries_added": len(sample)}


@router.post("/{meeting_id}/auto-join", response_model=MeetingStatusRead)
def set_auto_join(
    meeting_id: int,
    payload: AutoJoinUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    meeting = _get_org_meeting(db, meeting_id, current_user.organization_id)

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if not meeting.join_url:
        raise HTTPException(status_code=400, detail="Meeting has no Google Meet URL")

    meeting.auto_join = payload.enabled
    db.commit()
    db.refresh(meeting)

    print("\n==============================")
    print("AUTO JOIN REQUEST RECEIVED")
    print(f"Meeting ID : {meeting.id}")
    print(f"Org ID     : {meeting.organization_id}")
    print(f"Title      : {meeting.title}")
    print(f"Status     : {meeting.status}")
    print(f"Auto Join  : {meeting.auto_join}")
    print(f"Starts At  : {meeting.starts_at}")
    print(f"Now        : {datetime.utcnow()}")
    print("==============================\n")

    should_join_now = (
        payload.enabled
        and meeting.status in ("scheduled", "failed")
        and meeting.join_url
        and (meeting.starts_at is None or meeting.starts_at <= datetime.utcnow())
        and (meeting.ends_at is None or meeting.ends_at >= datetime.utcnow())
    )

    print(f"[AUTO JOIN] should_join_now = {should_join_now}")

    if should_join_now:
        print(f"[AUTO JOIN] Launching bot for meeting {meeting.id}")
        result = MeetingBotService().join(
            meeting.provider,
            meeting.join_url,
            meeting_id=meeting.id,
        )
        print(f"[AUTO JOIN RESULT] {result}")

    return meeting


@router.get("/{meeting_id}/status", response_model=MeetingStatusRead)
def meeting_status(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Meeting:
    meeting = _get_org_meeting(db, meeting_id, current_user.organization_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.get("/{meeting_id}/transcript", response_model=TranscriptResponse)
def get_transcript(
    meeting_id: int,
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Live Transcript Page data source.

    Supports an optional ``q`` search query that filters transcript entries
    by text or speaker (case-insensitive substring match).
    """
    meeting = _get_org_meeting(db, meeting_id, current_user.organization_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    query = db.query(Transcript).filter(Transcript.meeting_id == meeting_id)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            (Transcript.text.ilike(like)) | (Transcript.speaker.ilike(like))
        )
    entries = query.order_by(Transcript.id.asc()).all()

    return {
        "meeting_id": meeting.id,
        "status": meeting.status,
        "entries": [TranscriptEntryRead.model_validate(entry) for entry in entries],
    }
