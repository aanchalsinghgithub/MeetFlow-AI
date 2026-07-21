import logging
import os

from sqlalchemy.orm import Session

from app.models.entities import Meeting, Participant
from app.repositories.task_repository import TaskRepository
from app.schemas.meeting import ProcessTranscriptRequest, ProcessTranscriptResponse
from app.schemas.task import TaskRead
from app.services.approval_service import ApprovalService
from app.services.email_service import EmailService
from app.services.mistral_service import MistralService
from app.services.task_extractor import TaskExtractor

logger = logging.getLogger(__name__)


class MeetingPipeline:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.extractor = TaskExtractor()
        self.tasks = TaskRepository(db)
        self.approvals = ApprovalService(db)
        self.mistral = MistralService()
        self.email = EmailService()

    async def process_transcript(self, payload: ProcessTranscriptRequest) -> ProcessTranscriptResponse:
        meeting = self._get_or_create_meeting(payload)
        rendered_transcript = [
            turn.model_dump(exclude_none=True)
            for turn in payload.transcript
        ]
        meeting.transcript = rendered_transcript
        summary = await self.mistral.summarize_meeting(self._render_transcript(payload))
        meeting.summary = summary.get("executive_summary")
        meeting.decisions = summary.get("decisions_taken", [])
        # BUGFIX: these three were being requested from Mistral (see the
        # system prompt in mistral_service.py) and thrown away right here -
        # never saved, never shown anywhere. That's most of what "purpose /
        # what was discussed" actually needs beyond one summary paragraph.
        meeting.key_discussion_points = summary.get("key_discussion_points", [])
        meeting.risks = summary.get("risks", [])
        meeting.blockers = summary.get("blockers", [])
        self.db.commit()
        self.db.refresh(meeting)

        task_payloads = await self.extractor.extract(payload.transcript)
        created = []
        for task_payload in task_payloads:
            task_payload.meeting_id = meeting.id
            task = self.tasks.create(task_payload)
            self.approvals.create_manager_review(task.id)
            created.append(TaskRead.model_validate(task))

        # Send the meeting recap to every participant with a real email
        # address - independent of task approval (see approval_service.py,
        # which only emails the person a specific task is assigned to).
        recipients = [p.email for p in meeting.participants if p.email]
        if not recipients:
            # TESTING: meeting.participants comes from Google Calendar
            # attendees (calendar_service.py) or a manually-entered list;
            # test/demo meetings often have none with real emails. Fall back
            # to the same test recipient used elsewhere so the summary email
            # is still visibly sent while testing, instead of the loop below
            # silently doing nothing.
            fallback = (
                os.environ.get("MEETING_SUMMARY_TEST_EMAIL")
                or os.environ.get("TASK_ASSIGNMENT_TEST_EMAIL")
                or "aanchal2025.singh@gmail.com"
            )
            logger.info(
                "No participant emails found for meeting %s - falling back to test recipient %s",
                meeting.id,
                fallback,
            )
            recipients = [fallback]

        for recipient_email in recipients:
            logger.info("=========================")
            logger.info("MEETING SUMMARY EMAIL")
            logger.info("Meeting ID: %s", meeting.id)
            logger.info("Recipient: %s", recipient_email)
            logger.info("=========================")
            try:
                self.email.meeting_summary(recipient_email, meeting)
            except Exception as e:
                logger.warning("Failed to email meeting summary to %s: %s", recipient_email, e)

        return ProcessTranscriptResponse(meeting=meeting, tasks=created)

    def _get_or_create_meeting(self, payload: ProcessTranscriptRequest) -> Meeting:
        if payload.meeting_id:
            meeting = self.db.get(Meeting, payload.meeting_id)
            if meeting:
                return meeting

        meeting = Meeting(title=payload.meeting_title)
        self.db.add(meeting)
        self.db.flush()
        for participant in payload.participants:
            self.db.add(
                Participant(
                    meeting_id=meeting.id,
                    name=participant,
                    email=participant if "@" in participant else None,
                )
            )
        self.db.commit()
        self.db.refresh(meeting)
        return meeting

    @staticmethod
    def _render_transcript(payload: ProcessTranscriptRequest) -> str:
        return "\n".join(
            f"[{turn.timestamp or '--:--'}] {turn.speaker}: {turn.text}"
            for turn in payload.transcript
        )
