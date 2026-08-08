"""MeetFlow meeting bot: joins a Google Meet call with Playwright.

Audio is now captured by the Electron desktop app via Windows WASAPI Loopback.
Chunks arrive at POST /api/meetings/{meeting_id}/audio.
This bot only handles browser automation and meeting lifecycle.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

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
        # Clear any stale error from a previous failed attempt (the scheduler
        # retries FAILED meetings, so without this the old message would
        # linger in the UI even after a successful join).
        self._set_status(MeetingStatus.BOT_JOINING, error=None)

        bot_name = self._bot_display_name()

        try:
            with self._launch_browser() as page:
                self._join_meeting(page, bot_name)
                self._set_status(MeetingStatus.IN_PROGRESS, error=None)
                self._monitor(page)
        except Exception as exc:
            # BUGFIX: the exception was logged to stdout only. Render's logs
            # aren't visible from the app, so the UI just showed a bare
            # "failed" badge with no way to know why. Now the message is
            # persisted on the meeting and returned to the frontend.
            logger.exception("Meeting bot failed for meeting %s", self.meeting_id)
            self._set_status(MeetingStatus.FAILED, error=str(exc)[:2000])
            return

        if not self._stop_event.is_set():
            self._set_status(MeetingStatus.COMPLETED, error=None)

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

            from app.core.config import settings

            with sync_playwright() as playwright:
                # NOTE: no user_data_dir / persistent profile here on purpose.
                # This app is multi-tenant and Render has no display, so each
                # meeting gets its own fresh, isolated, headless context and
                # joins as an anonymous guest (no Google login needed).
                #
                # BUGFIX: this worked locally but failed on Render. Two very
                # common Docker/cloud-container gotchas for Chromium that a
                # normal local machine never hits:
                #   --disable-dev-shm-usage — containers often only give
                #     Chromium a tiny /dev/shm (Render included), and Chrome
                #     crashes or silently misbehaves once it runs out.
                #   --no-sandbox — Chrome's sandbox needs a kernel privilege
                #     (CAP_SYS_ADMIN) that most container platforms, Render
                #     included, don't grant; without this flag the browser
                #     can fail to launch at all.
                # Also gave the context a realistic desktop viewport/UA/locale
                # — a cloud datacenter IP is already a bot signal to Google,
                # no reason to add "tiny headless viewport, no locale" on top.
                browser = playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--use-fake-ui-for-media-stream",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                    ],
                )

                # NEW: join as a real logged-in Google account instead of an
                # anonymous guest, if a saved session exists. This is a
                # *reused* session only — we deliberately never do a live
                # email/password login here. An automated login attempt from
                # a fresh headless cloud browser hits the exact same
                # "unusual traffic" block as anonymous joins did, usually
                # worse, since Google scrutinizes login flows harder than
                # page views. The session must be generated once, locally,
                # in a real headed browser (see scripts/save_google_session.py),
                # then reused here as-is.
                storage_state_path = Path(settings.google_bot_storage_state_path)
                context_kwargs: dict = dict(
                    permissions=["camera", "microphone"],
                    viewport={"width": 1366, "height": 768},
                    locale="en-US",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    ),
                )
                if storage_state_path.exists():
                    print(f"Using saved Google session: {storage_state_path}")
                    context_kwargs["storage_state"] = str(storage_state_path)
                else:
                    print(
                        f"No saved Google session at {storage_state_path} — "
                        "joining as anonymous guest."
                    )

                context = browser.new_context(**context_kwargs)
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

        # BUGFIX: wait_until="networkidle" almost never resolves on Google
        # Meet. Meet is a SPA that keeps a persistent websocket open for
        # real-time signalling, so the network connection count never drops
        # to zero — Playwright would wait the full 60s and then throw a
        # TimeoutError, which was caught by run()'s except block and marked
        # the meeting FAILED *before* any of the debug screenshot / button
        # detection code below ever ran. That's why failures were happening
        # with no useful debug output. "domcontentloaded" is what we
        # actually need here; we then poll for the pre-join UI ourselves.
        page.goto(self.join_url, wait_until="domcontentloaded", timeout=30000)
        print("Current URL:", page.url)

        # NEW: if we're using a saved Google session and it's expired/been
        # revoked, Google redirects to its own sign-in page instead of the
        # Meet pre-join screen. Catch that specifically — otherwise it just
        # falls through to the generic "could not find join button" error,
        # which doesn't tell you the session needs regenerating.
        if "accounts.google.com" in page.url:
            raise RuntimeError(
                "Saved Google session is expired or invalid — Google redirected to "
                "its sign-in page. Regenerate it with scripts/save_google_session.py."
            )

        try:
            print("Page Title:", page.title())
        except Exception as e:
            print("Title Error:", e)

        # Give the Meet SPA a moment to render the pre-join screen (name
        # field / Ask to join / an error like "meeting code was not valid").
        body_text = ""
        for _ in range(15):
            try:
                body_text = page.locator("body").inner_text()
            except Exception:
                body_text = ""
            if any(
                marker in body_text.lower()
                for marker in ("your name", "ask to join", "join now", "meeting code", "can't join", "can't create")
            ):
                break
            page.wait_for_timeout(1000)

        try:
            page.screenshot(path=f"meet_debug_{self.meeting_id}.png", full_page=True)
            print("Screenshot saved")
        except Exception as e:
            print("Screenshot Error:", e)

        print("\n========== PAGE CONTENT ==========")
        print(body_text[:5000])
        print("========== END PAGE CONTENT ==========\n")

        # BUGFIX: previously *every* join failure raised the same generic
        # "Could not find join button" error regardless of cause, so there
        # was no way to tell an invalid/expired link apart from the host
        # blocking guest entry. Detect Meet's own error screens up front so
        # the stored error_message is actually actionable.
        error_markers = {
            "meeting code was not valid": "Invalid or expired Google Meet link.",
            "check your meeting code": "Invalid or expired Google Meet link.",
            "you can't join this video call": "Guest joining is blocked for this meeting (host restricted access).",
            "you can't join this call": "Guest joining is blocked for this meeting (host restricted access).",
            "this meeting has been ended": "The meeting was already ended.",
            "denied entry": "The bot was denied entry by the host.",
            "meeting doesn't exist": "Invalid or expired Google Meet link.",
            "this browser or app may not be secure": "Google blocked this as an insecure/automated browser (cloud server IP flagged as a bot).",
            "couldn't sign you in": "Google blocked this as an insecure/automated browser (cloud server IP flagged as a bot).",
            "unusual traffic": "Google flagged this server's IP address as automated traffic.",
        }
        lowered = body_text.lower()
        for marker, message in error_markers.items():
            if marker in lowered:
                raise RuntimeError(message)

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

        raise RuntimeError(
            f"Could not find a join button (Ask to join / Join now) on the Meet pre-join "
            f"screen for meeting {self.meeting_id}. See meet_debug_{self.meeting_id}.png and "
            f"after_join_attempt_{self.meeting_id}.png for what the page actually looked like."
        )

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
    def _set_status(self, status: MeetingStatus, error: str | None = None) -> None:
        db = SessionLocal()
        try:
            meeting = db.get(Meeting, self.meeting_id)
            if meeting:
                print(
                    f"[MeetingBot {self.meeting_id}] "
                    f"org={meeting.organization_id} status: {meeting.status} -> {status.value}"
                    + (f" error={error!r}" if error else "")
                )
                meeting.status = status.value
                meeting.error_message = error
                db.commit()
        finally:
            db.close()
