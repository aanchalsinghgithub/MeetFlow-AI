"""Run this ONCE on your own computer (not on Render) to let the MeetFlow
bot join meetings as a real logged-in Google account instead of an
anonymous guest.

Why this has to be done locally, by hand:
Google actively blocks automated email/password logins from a fresh
headless browser on a cloud/datacenter IP — the exact same "unusual
traffic" wall the anonymous guest join was hitting on Render, except
Google scrutinizes login attempts even harder than page views. There is
no reliable way to script the login itself on the server.

The workaround every meeting-bot tool uses: log in for real, once, in a
real headed browser on a real residential IP (your laptop), complete any
2FA/"is this you?" prompts Google throws up, and save the resulting
session cookies. The server then *reuses* that already-authenticated
session — it never performs a login of its own.

Usage:
    cd backend
    uv run playwright install chromium      # first time only
    uv run python scripts/save_google_session.py

A real Chrome window will open to the Google sign-in page. Log in with
whichever Google account you want the bot to appear as (create a
dedicated one for this — don't use your personal account). Once you land
on a normal Google page (e.g. myaccount.google.com) after finishing any
verification steps, come back to the terminal and press Enter.

This writes google_auth_state.json in the backend folder. That file
contains live session cookies — treat it like a password:
  - It's already in .gitignore. Never commit it.
  - On Render, upload it via "Secret Files" (Render dashboard -> your
    service -> Environment -> Secret Files) mounted at the same path
    GOOGLE_BOT_STORAGE_STATE_PATH points to (default: google_auth_state.json
    in the backend working directory).
  - Google sessions can eventually expire or get invalidated (e.g. if
    you change the account password, or Google flags the Render IP and
    forces re-verification). If meeting_bot.py starts raising "Saved
    Google session is expired or invalid", just rerun this script and
    re-upload the new file.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "google_auth_state.json"


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://accounts.google.com/", wait_until="domcontentloaded")

        print("\n" + "=" * 70)
        print("A Chrome window has opened. Log in with the Google account you")
        print("want the MeetFlow bot to join meetings as.")
        print("Complete any 2-factor / 'verify it's you' steps Google asks for.")
        print("Once you're signed in and on a normal Google page, come back")
        print("here and press Enter.")
        print("=" * 70 + "\n")
        input("Press Enter once you're fully signed in... ")

        context.storage_state(path=str(OUTPUT_PATH))
        print(f"\nSaved session to: {OUTPUT_PATH}")
        print("Upload this file to Render as a Secret File before deploying.")

        browser.close()


if __name__ == "__main__":
    main()
