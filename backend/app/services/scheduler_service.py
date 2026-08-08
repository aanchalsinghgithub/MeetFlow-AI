"""Scheduler for the Auto Join workflow.

Runs an APScheduler background job every minute that:

* Looks for meetings with ``auto_join=True`` and ``status="scheduled"``.
* Finds meetings starting within the next minute (or already started but
  not yet picked up).
* Launches :class:`app.services.meeting_bot.MeetingBot` for each one.

Started from ``app.main`` on FastAPI startup and shut down on FastAPI
shutdown.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.models.entities import Meeting
from app.models.enums import MeetingStatus
from app.services.meeting_bot import MeetingBot

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 15
JOIN_WINDOW_MINUTES = 60


class SchedulerService:
    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        self._scheduler.add_job(
            self.check_upcoming_meetings,
            "interval",
            seconds=CHECK_INTERVAL_SECONDS,
            id="meetflow-auto-join-check",
            replace_existing=True,
            max_instances=1,
        )
        self._scheduler.start()
        logger.info("MeetFlow scheduler started (interval=%ss)", CHECK_INTERVAL_SECONDS)

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    def check_upcoming_meetings(self) -> None:
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            window_end = now + timedelta(minutes=JOIN_WINDOW_MINUTES)
            print("\n========== SCHEDULER ==========")
            print("NOW UTC:", now)
            print("WINDOW END:", window_end)
            all_meetings = (
                db.query(Meeting)
                .filter(Meeting.auto_join.is_(True))
                .all()
            )
              
            for m in all_meetings:
                print(
                 f"Meeting={m.id} "
                 f"Org={m.organization_id} "
                 f"Title={m.title} "
                 f"Start={m.starts_at} "
                 f"Status={m.status} "
                 f"AutoJoin={m.auto_join}"
                )

            print("===============================\n")

            

            # BUGFIX: this query had no lower bound on starts_at, so a
            # meeting that failed to join once (e.g. bad link, host blocked
            # the bot) got relaunched again every 15s *forever* — including
            # meetings that started hours or days ago. That's a retry storm,
            # not a retry. FAILED meetings are now only retried while still
            # inside the same join window we'd use for a fresh join.
            retry_after = now - timedelta(minutes=JOIN_WINDOW_MINUTES)
            due_meetings = (
                db.query(Meeting)
                .filter(
                    Meeting.auto_join.is_(True),
                    Meeting.status.in_([MeetingStatus.SCHEDULED.value, MeetingStatus.FAILED.value]),
                    Meeting.join_url.isnot(None),
                    Meeting.starts_at.isnot(None),
                    Meeting.starts_at <= window_end,
                    Meeting.starts_at >= retry_after,
                )
                .all()
            )

            for meeting in due_meetings:
                if meeting.ends_at and meeting.ends_at < now:
                    # Meeting already finished before the bot could join.
                    meeting.status = MeetingStatus.COMPLETED.value
                    continue

                logger.info(
                    "Auto-join triggered for org %s meeting %s (%s)",
                    meeting.organization_id,
                    meeting.id,
                    meeting.title,
                )
                MeetingBot(meeting_id=meeting.id, join_url=meeting.join_url).start_async()

            db.commit()
        except Exception:
            logger.exception("Scheduler check_upcoming_meetings failed")
        finally:
            db.close()


scheduler_service = SchedulerService()
