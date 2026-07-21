import logging
import smtplib
import traceback
from email.message import EmailMessage

from app.core.config import settings
from app.models.entities import Meeting, Task

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Raised when an email fails to send, carrying the exact reason.

    Used instead of letting smtplib exceptions propagate raw, and instead of
    silently swallowing them - callers that need to know the send failed
    (e.g. the approval flow) can catch this and surface `str(e)` to the
    caller/UI; callers that treat email as best-effort (meeting summary
    notifications) can keep calling `send()` with raise_on_failure=False.
    """


def _format_risk(item) -> str:
    """Meeting.risks is a raw JSON column - old rows may hold plain strings,
    new rows hold {"risk", "impact", "mitigation"} dicts (see
    app/schemas/meeting.py::RiskItem). Format either shape as one readable
    line instead of assuming a fixed structure."""
    if isinstance(item, dict):
        risk = (item.get("risk") or "").strip() or "(unspecified risk)"
        details = []
        if item.get("impact"):
            details.append(f"Impact: {item['impact']}")
        if item.get("mitigation"):
            details.append(f"Mitigation: {item['mitigation']}")
        return f"- {risk}" + (f" ({'; '.join(details)})" if details else "")
    return f"- {item}"


def _format_blocker(item) -> str:
    """Same idea as _format_risk, for Meeting.blockers /
    app/schemas/meeting.py::BlockerItem."""
    if isinstance(item, dict):
        blocker = (item.get("blocker") or "").strip() or "(unspecified blocker)"
        details = []
        if item.get("impact"):
            details.append(f"Impact: {item['impact']}")
        if item.get("owner"):
            details.append(f"Owner: {item['owner']}")
        if item.get("action"):
            details.append(f"Next step: {item['action']}")
        return f"- {blocker}" + (f" ({'; '.join(details)})" if details else "")
    return f"- {item}"


class EmailService:
    def send(
        self,
        to_email: str,
        subject: str,
        body: str,
        *,
        raise_on_failure: bool = False,
    ) -> bool:
        """Send a single email.

        Returns True if the message was handed off to the SMTP server
        successfully, False otherwise. If raise_on_failure is True, failures
        raise EmailSendError(str(original_exception)) instead of returning
        False, so the caller can report the exact reason upstream.
        """
        if not settings.smtp_host:
            reason = (
                "SMTP_HOST is not configured (settings.smtp_host is empty). "
                "Check that backend/.env exists, is in the working directory "
                "the app was started from, and contains SMTP_HOST=... - "
                "Settings() reads it via pydantic-settings' env_file loader."
            )
            logger.error(reason)
            if raise_on_failure:
                raise EmailSendError(reason)
            return False

        if not settings.smtp_username or not settings.smtp_password:
            logger.warning(
                "SMTP_USERNAME and/or SMTP_PASSWORD are not set - attempting "
                "an unauthenticated send to %s, which Gmail will reject.",
                to_email,
            )

        message = EmailMessage()
        message["From"] = settings.smtp_username or "noreply@meetflow.ai"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
                smtp.starttls()

                logger.info("=========================")
                logger.info("SMTP CONNECTED")
                logger.info("=========================")

                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password)

                smtp.send_message(message)
        except (smtplib.SMTPException, OSError) as e:
            # BUGFIX: this used to just `logger.warning(...)` and move on,
            # which is why "approval emails are never received" was silent -
            # nothing ever showed the actual SMTP error (e.g. Gmail
            # rejecting a raw account password instead of an App Password).
            # Now: log the full traceback AND optionally raise, so the
            # approval flow can report the exact reason instead of pretending
            # the email went out.
            logger.error("=========================")
            logger.error("EMAIL SEND FAILED")
            logger.error("Recipient: %s", to_email)
            logger.error("Reason: %s: %s", type(e).__name__, e)
            logger.error("=========================")
            logger.error("Full exception:\n%s", traceback.format_exc())
            if raise_on_failure:
                raise EmailSendError(f"{type(e).__name__}: {e}") from e
            return False

        logger.info("=========================")
        logger.info("EMAIL SENT SUCCESSFULLY")
        logger.info("Recipient: %s", to_email)
        logger.info("=========================")
        return True

    def meeting_summary(self, participant_email: str, meeting: Meeting) -> None:
        """Send the meeting recap to ONE participant.

        Called once per participant with a real email address, from
        MeetingPipeline.process_transcript() right after a meeting is
        finalized - NOT per task approval. Every attendee gets the same
        summary regardless of who ends up owning which task; this is
        deliberately independent of the approval flow in approval_service.py,
        which only emails the person a specific task gets assigned to.
        """
        lines = [
            f"Meeting: {meeting.title}",
            "",
            "SUMMARY:",
            meeting.summary or "Summary pending.",
            "",
            "DECISIONS:",
        ]
        if meeting.decisions:
            lines.extend(f"- {item}" for item in meeting.decisions)
        else:
            lines.append("- None recorded.")

        lines.append("")
        lines.append("ACTION ITEMS FROM THIS MEETING:")
        if meeting.tasks:
            lines.extend(
                f"- {t.title} (Owner: {t.owner or 'unassigned'}, Status: {t.status})" for t in meeting.tasks
            )
        else:
            lines.append("- None extracted.")

        lines.append("")
        lines.append("RISKS:")
        if meeting.risks:
            lines.extend(_format_risk(r) for r in meeting.risks)
        else:
            lines.append("- None identified.")

        lines.append("")
        lines.append("BLOCKERS:")
        if meeting.blockers:
            lines.extend(_format_blocker(b) for b in meeting.blockers)
        else:
            lines.append("- None identified.")

        body = "\n".join(lines)
        self.send(participant_email, f"Meeting Summary: {meeting.title}", body)

    def approval_request(self, manager_email: str, task: Task) -> None:
        body = (
            f"Task: {task.title}\n"
            f"Owner: {task.owner}\n"
            f"Mentioned By: {task.mentioned_by}\n"
            f"Requested By: {task.requested_by}\n"
            f"Deadline: {task.deadline}\n"
            f"Priority: {task.priority}\n"
            f"Confidence: {task.confidence:.0%}\n\n"
            "Review in MeetFlow AI to Approve, Edit, or Reject."
        )
        self.send(manager_email, f"Approval Required: {task.title}", body)

    def task_assignment(self, assignee_email: str, task: Task, manager_name: str) -> bool:
        """Send the post-approval "task assigned" email."""
        body = (
            f"Task Name: {task.title}\n"
            f"Task Description: {task.description or task.title}\n"
            f"Meeting ID: {task.meeting_id}\n"
            f"Who Mentioned It: {task.mentioned_by}\n"
            f"Who Requested It: {task.requested_by}\n"
            f"Deadline: {task.deadline}\n"
            f"Priority: {task.priority}\n"
            f"Dependencies: {', '.join(task.dependencies or [])}\n"
            f"Manager Name: {manager_name}\n"
        )
        # raise_on_failure=True: this is the post-approval email. The
        # approval flow needs to know if it actually went out (and why not),
        # rather than silently pretending it did.
        return self.send(
            assignee_email,
            f"Task Assigned: {task.title}",
            body,
            raise_on_failure=True,
        )
