"""Run this AFTER scripts/save_google_session.py, once per organization.

save_google_session.py logs in once locally and writes google_auth_state.json
to disk. This script uploads that file to your MeetFlow backend so it's
stored against *your* organization (via your login token) instead of being
one global file shared by every tenant.

Usage:
    cd backend
    uv run python scripts/upload_google_session.py \
        --backend-url https://meetflow-backend-moit.onrender.com \
        --email meetflow.notetaker@gmail.com \
        --user-email you@yourcompany.com

You'll be prompted for your MeetFlow password (not left in shell history).

--email is the Google account save_google_session.py logged into (just
stored for your own reference, shown back by GET /organizations/google-bot-session).
--user-email / password are YOUR MeetFlow login (not the bot's) — used to
get an access token so the upload lands on your organization.

Uses only the Python standard library (urllib) — no extra pip install needed.
"""

from __future__ import annotations

import argparse
import getpass
import json
import urllib.error
import urllib.request
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "google_auth_state.json"


def _post_json(url: str, payload: dict, token: str | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        # BUGFIX: Render's free tier spins the service down after ~15 min
        # idle, and the first request after that can take 30-60s to wake it
        # back up — a plain 30s timeout was tripping on exactly that, not a
        # real failure. Bumped to 90s, and the specific timeout case now
        # says so instead of just dumping a raw traceback.
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Request to {url} failed ({exc.code}): {body}") from exc
    except TimeoutError:
        raise SystemExit(
            f"Timed out waiting for {url}. If your backend is on Render's "
            "free tier, it may have been asleep — just run this command "
            "again, the first request wakes it up."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend-url", required=True, help="e.g. https://meetflow-backend-moit.onrender.com")
    parser.add_argument("--email", required=True, help="The Google account the bot logged in as")
    parser.add_argument("--user-email", required=True, help="Your MeetFlow login email")
    parser.add_argument("--state-file", default=str(STATE_FILE), help="Path to google_auth_state.json")
    args = parser.parse_args()

    password = getpass.getpass("MeetFlow password: ")

    state_path = Path(args.state_file)
    if not state_path.exists():
        raise SystemExit(
            f"No session file at {state_path}. Run scripts/save_google_session.py first."
        )
    storage_state = json.loads(state_path.read_text())

    backend_url = args.backend_url.rstrip("/")

    print("Logging in to MeetFlow...")
    login_result = _post_json(
        f"{backend_url}/api/auth/login",
        {"email": args.user_email, "password": password},
    )
    token = login_result["access_token"]

    print("Uploading Google session...")
    upload_result = _post_json(
        f"{backend_url}/api/organizations/google-bot-session",
        {"email": args.email, "storage_state": storage_state},
        token=token,
    )

    print("Done:", upload_result)
    print(
        "\nYour organization's bot will now join meetings as "
        f"{args.email} instead of an anonymous guest."
    )


if __name__ == "__main__":
    main()
