import logging
import os

from sqlalchemy.orm import Session

from app.models.enums import ApprovalDecision, TaskStatus
from app.repositories.task_repository import TaskRepository
from app.schemas.task import ApprovalUpdate
from app.services.email_service import EmailSendError, EmailService
from app.services.team_mapping import leader_for_domain

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TESTING ONLY: post-approval "task assigned" emails default to this address
# instead of the real task owner (task.owner is currently a name like
# "Aanchal", not an email address, so there is no real owner inbox to send
# to yet anyway). Precedence, highest first:
#   1. payload.recipient_email - per-task override sent from the Approval
#      Queue's Edit form ("Send approval email to" field).
#   2. TASK_ASSIGNMENT_TEST_EMAIL in .env.
#   3. _DEFAULT_TEST_RECIPIENT below.
# There's always a fallback, so "ALWAYS send" still holds even if nothing
# overrides it.
#
# To restore real per-owner delivery later: stop falling back to
# _DEFAULT_TEST_RECIPIENT / TASK_ASSIGNMENT_TEST_EMAIL and route on
# task.owner (once task.owner is wired up to actual email addresses via
# team_mapping.json's roster).
# ---------------------------------------------------------------------------
_DEFAULT_TEST_RECIPIENT = "aanchal2025.singh@gmail.com"
_TASK_ASSIGNMENT_TEST_EMAIL = os.environ.get("TASK_ASSIGNMENT_TEST_EMAIL") or _DEFAULT_TEST_RECIPIENT


class ApprovalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.tasks = TaskRepository(db)
        self.email = EmailService()

    def create_manager_review(self, task_id: int) -> None:
        task = self.tasks.get(task_id)
        if not task:
            return
        manager_email = leader_for_domain(task.domain) or "manager@company.com"
        self.tasks.add_approval(task.id, manager_email)
        self.email.approval_request(manager_email, task)

    def decide(self, task_id: int, payload: ApprovalUpdate) -> dict:
        """Apply an approval decision and (if approved/edited) send the
        task-assignment email.

        Returns a dict describing what happened to the email so the route
        layer can report it back to the caller instead of swallowing it:
            {
                "attempted": bool,
                "sent": bool,
                "recipient": str | None,
                "error": str | None,
            }
        The task's approval decision itself always commits regardless of
        whether the email succeeds - a failed email must never roll back or
        block the approval.
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError("Task not found")

        if payload.edited_task:
            edited = payload.edited_task
            task.title = edited.title
            task.description = edited.description
            task.owner = edited.owner
            task.deadline = edited.deadline
            task.priority = edited.priority.value
            task.domain = edited.domain
            task.dependencies = edited.dependencies
            task.confidence = edited.confidence

        decision = ApprovalDecision(payload.decision)
        approval = self.tasks.latest_approval(task.id)
        if approval:
            approval.decision = decision.value
            approval.edited_payload = payload.edited_task.model_dump(mode="json") if payload.edited_task else None
            approval.notes = payload.notes

        task.status = {
            ApprovalDecision.APPROVED: TaskStatus.ASSIGNED.value,
            ApprovalDecision.EDITED: TaskStatus.ASSIGNED.value,
            ApprovalDecision.REJECTED: TaskStatus.REJECTED.value,
        }.get(decision, TaskStatus.REVIEW_REQUIRED.value)
        self.db.commit()

        email_status = {"attempted": False, "sent": False, "recipient": None, "error": None}

        if task.status == TaskStatus.ASSIGNED.value:
            # NEW: the Approval Queue's Edit form can send an explicit
            # recipient_email to override where this one task's assignment
            # email goes. Falls back to the hardcoded test recipient when
            # not provided (or blank/whitespace-only).
            override = (payload.recipient_email or "").strip()
            recipient = override or _TASK_ASSIGNMENT_TEST_EMAIL
            email_status["attempted"] = True
            email_status["recipient"] = recipient

            # Keep the "Goes to" address shown in the Approval Queue in sync
            # with where the email actually went, so re-opening this task
            # later reflects reality instead of the original routing.
            if approval:
                approval.manager_email = recipient

            logger.info("=========================")
            logger.info("APPROVAL STARTED")
            logger.info("Meeting ID: %s", task.meeting_id)
            logger.info("Task ID: %s", task.id)
            logger.info("Recipient: %s", recipient)
            logger.info("=========================")

            try:
                self.email.task_assignment(recipient, task, manager_name="Team Lead")
                email_status["sent"] = True
            except EmailSendError as e:
                # BUGFIX: this used to be `if recipient: self.email.task_assignment(...)`
                # with no try/except at all, and email_service.send() swallowed
                # every SMTP exception internally - so "approve" always looked
                # like it worked even when Gmail rejected the login and no
                # email ever went out. Now the exact reason is logged here and
                # returned to the route so the API response reflects reality.
                logger.error(
                    "APPROVAL EMAIL FAILED for task %s (meeting %s), recipient %s: %s",
                    task.id,
                    task.meeting_id,
                    recipient,
                    e,
                )
                email_status["error"] = str(e)

        return email_status
