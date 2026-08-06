"""MeetFlow meeting bot: joins a Google Meet call with Playwright.

Audio is now captured by the Electron desktop app via Windows WASAPI Loopback.
Chunks arrive at POST /api/meetings/{meeting_id}/audio.
This bot only handles browser automation and meeting lifecycle.
"""
from __future__ import annotations

import logging
import threading
import time

from app.core.database import SessionLocal
from app.models.entities import Meeting, Organization
from app.models.enums import MeetingStatus

logger = logging.getLogger(__name__)

MEET_ENDED_SELECTORS = [
    "text=You left the meeting",
    "text=Return to home screen",
    "text=Meeting ended",
]


class MeetingBot:
    """Joins and monitors a Google Meet session.

    Audio capture is handled by the Electron desktop app via WASAPI loopback.
    Audio chunks are POSTed to /api/meetings/{meeting_id}/audio by Electron.
    """

    def __init__(self, meeting_id: int, join_url: str) -> None:
        self.meeting_id = meeting_id
        self.join_url = join_url
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public entrypoints
    # ------------------------------------------------------------------
    def start_async(self) -> threading.Thread:
        thread = threading.Thread(
            target=self.run,
            name=f"meeting-bot-{self.meeting_id}",
            daemon=True,
        )
        thread.start()
        return thread

    def stop(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        print(f"\n===== BOT STARTED FOR MEETING {self.meeting_id} =====\n")
        self._set_status(MeetingStatus.BOT_JOINING)

        bot_name = self._bot_display_name()

        try:
            with self._launch_browser() as page:
                self._join_meeting(page, bot_name)
                self._set_status(MeetingStatus.IN_PROGRESS)
                self._monitor(page)
        except Exception:
            logger.exception("Meeting bot failed for meeting %s", self.meeting_id)
            self._set_status(MeetingStatus.FAILED)
            return

        if not self._stop_event.is_set():
            self._set_status(MeetingStatus.COMPLETED)

    # ------------------------------------------------------------------
    # Multi-tenant bot identity
    # ------------------------------------------------------------------
    def _bot_display_name(self) -> str:
        """Build a per-organization guest name, e.g. 'Acme Corp Notetaker'.

        No Google login/profile is used, so this works identically for
        every tenant and never collides across organizations.
        """
        db = SessionLocal()
        try:
            meeting = db.get(Meeting, self.meeting_id)
            if meeting:
                org = db.get(Organization, meeting.organization_id)
                if org:
                    return f"{org.name} Notetaker"
        finally:
            db.close()
        return "MeetFlow Notetaker"

    # ------------------------------------------------------------------
    # Browser control
    # ------------------------------------------------------------------
    def _launch_browser(self):
        from contextlib import contextmanager

        @contextmanager
        def _context():
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                # NOTE: no user_data_dir / persistent profile here on purpose.
                # This app is multi-tenant and Render has no display, so each
                # meeting gets its own fresh, isolated, headless context and
                # joins as an anonymous guest (no Google login needed).
                browser = playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--use-fake-ui-for-media-stream",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                context = browser.new_context(permissions=["camera", "microphone"])
                page = context.new_page()
                try:
                    yield page
                finally:
                    context.close()
                    browser.close()

        return _context()

    def _join_meeting(self, page, bot_name: str) -> None:
        print("\n===================================")
        print("STEP 1: OPENING GOOGLE MEET")
        print("===================================\n")

        page.goto(self.join_url, wait_until="networkidle", timeout=60000)
        print("Current URL:", page.url)

        try:
            print("Page Title:", page.title())
        except Exception as e:
            print("Title Error:", e)

        try:
            page.screenshot(path=f"meet_debug_{self.meeting_id}.png", full_page=True)
            print("Screenshot saved")
        except Exception as e:
            print("Screenshot Error:", e)

        try:
            print("\n========== PAGE CONTENT ==========")
            print(page.locator("body").inner_text()[:5000])
            print("========== END PAGE CONTENT ==========\n")
        except Exception as e:
            print("Content Error:", e)

        try:
            name_input = page.get_by_placeholder("Your name")
            name_input.fill(bot_name, timeout=5000)
            print("SUCCESS: filled guest name ->", bot_name)
        except Exception:
            print("FAILED: could not find guest name field (may already be signed in)")

        for label in ["Turn off microphone", "Turn off camera"]:
            try:
                page.get_by_label(label).click(timeout=5000)
                print("SUCCESS:", label)
            except Exception:
                print("FAILED:", label)

        page.wait_for_timeout(5000)

        print("\n===== BUTTONS FOUND =====")
        try:
            print(page.locator("button").all_inner_texts())
        except Exception as e:
            print(e)
        print("=========================\n")

        join_labels = ["Ask to join", "Join now", "Switch here", "Join here too"]

        for label in join_labels:
            try:
                print("Trying role=button name=", label)
                page.get_by_role("button", name=label, exact=False).first.click(timeout=5000)
                print("SUCCESS (role):", label)
                page.wait_for_timeout(5000)
                return
            except Exception:
                print("FAILED (role):", label)

            try:
                print("Trying text substring:", label)
                page.get_by_text(label, exact=False).first.click(timeout=5000)
                print("SUCCESS (text):", label)
                page.wait_for_timeout(5000)
                return
            except Exception:
                print("FAILED (text):", label)

        already_in = [
            "text=Leave call",
            "text=You have joined",
            "[aria-label='Leave call']",
            "button:has-text('Leave call')",
        ]
        for selector in already_in:
            try:
                if page.locator(selector).is_visible(timeout=3000):
                    print("Already inside meeting — continuing.")
                    return
            except Exception:
                continue

        page.screenshot(path=f"after_join_attempt_{self.meeting_id}.png", full_page=True)

        print("\n===== FINAL PAGE CONTENT =====")
        try:
            print(page.locator("body").inner_text()[:5000])
        except Exception as e:
            print(e)
        print("=============================\n")

        raise RuntimeError(f"Could not find join button for meeting {self.meeting_id}")

    def _monitor(self, page) -> None:
        """Keep the browser session alive until meeting ends or bot is stopped.

        Audio chunks arrive via POST /api/meetings/{meeting_id}/audio from Electron.
        No audio processing happens here.
        """
        while not self._stop_event.is_set():
            if self._meeting_has_ended(page):
                print(f"[MeetingBot {self.meeting_id}] _meeting_has_ended() returned True — marking meeting completed")
                logger.info("Meeting %s has ended.", self.meeting_id)
                break
            time.sleep(2)

    @staticmethod
    def _meeting_has_ended(page) -> bool:
        for selector in MEET_ENDED_SELECTORS:
            try:
                if page.locator(selector).is_visible():
                    print(f"[MeetingBot] Ended-selector matched: {selector!r}")
                    return True
            except Exception:
                continue
        if page.is_closed():
            print("[MeetingBot] page.is_closed() returned True")
            return True
        return False

    # ------------------------------------------------------------------
    # Status persistence
    # ------------------------------------------------------------------
    def _set_status(self, status: MeetingStatus) -> None:
        db = SessionLocal()
        try:
            meeting = db.get(Meeting, self.meeting_id)
            if meeting:
                print(
                    f"[MeetingBot {self.meeting_id}] "
                    f"org={meeting.organization_id} status: {meeting.status} -> {status.value}"
                )
                meeting.status = status.value
                db.commit()
        finally:
            db.close()
