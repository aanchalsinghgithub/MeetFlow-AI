"""Converts a cookies.txt export (Netscape format) into the
google_auth_state.json that meeting_bot.py / upload_google_session.py
expect — WITHOUT ever launching an automated browser against Google.

Why this replaces the Playwright-based save_google_session.py:
Google detects that a browser is CDP-controlled (which is fundamentally
how Playwright/Selenium/Puppeteer all work, regardless of headless/headed,
regardless of using real Chrome vs bundled Chromium, regardless of an
already-authenticated profile) and blocks "Couldn't sign you in" on ANY
visit to a Google-owned page, not just the login form. There is no
Playwright-based workaround for this — it has to not use Playwright at all
for this step.

The reliable alternative: export cookies from a completely normal,
manually-used Chrome session using a browser extension (which reads
cookies via Chrome's own internal chrome.cookies API — the same API Chrome
itself uses, so it isn't "automation" from Google's perspective at all),
then just convert that export into the JSON shape Playwright expects.

One-time setup (all by hand, no scripts, completely normal Chrome use):
  1. Install the "Get cookies.txt LOCALLY" extension from the Chrome Web
     Store (open-source, MIT licensed, does the export entirely locally —
     search the store, don't use a random unofficial copy).
  2. In your normal Chrome (or the dedicated "MeetFlow Bot" profile if you
     made one), sign in to the bot's Google account as usual.
  3. Go to https://meet.google.com while signed in (so Meet-relevant
     cookies definitely exist, not just the general google.com ones).
  4. Click the extension icon -> Export -> save as cookies.txt into this
     backend folder (or note the path you saved it to).

Then run:
    cd backend
    uv run python scripts/convert_cookies.py --cookies-file cookies.txt

This writes google_auth_state.json — from here, the rest of the flow is
unchanged: scripts/upload_google_session.py uploads it to your org.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "google_auth_state.json"


def parse_netscape_cookies(path: Path) -> list[dict]:
    cookies = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        http_only = False
        if line.startswith("#HttpOnly_"):
            http_only = True
            line = line[len("#HttpOnly_"):]
        elif line.startswith("#"):
            continue  # a regular comment line, e.g. the file header

        parts = line.split("\t")
        if len(parts) != 7:
            continue  # skip anything that doesn't match the expected shape

        domain, _include_subdomains, path_, secure, expiry, name, value = parts

        expires_seconds = int(expiry) if expiry.isdigit() and expiry != "0" else -1

        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path_ or "/",
                "expires": expires_seconds,
                "httpOnly": http_only,
                "secure": secure.upper() == "TRUE",
                # Netscape format has no sameSite concept — "Lax" is the
                # safe default for a same-site, direct-navigation use case
                # like this (no cross-site iframes involved).
                "sameSite": "Lax",
            }
        )
    return cookies


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cookies-file", required=True, help="Path to the exported cookies.txt")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Where to write google_auth_state.json")
    args = parser.parse_args()

    cookies_path = Path(args.cookies_file)
    if not cookies_path.exists():
        raise SystemExit(f"Cookie file not found: {cookies_path}")

    cookies = parse_netscape_cookies(cookies_path)
    google_cookies = [c for c in cookies if "google.com" in c["domain"]]

    if not google_cookies:
        raise SystemExit(
            "No google.com cookies found in that export. Make sure you were "
            "signed in and on a google.com/meet.google.com page when you "
            "exported."
        )

    critical = {"SID", "HSID", "SSID", "__Secure-1PSID", "__Secure-3PSID"}
    found_critical = {c["name"] for c in google_cookies} & critical
    if not found_critical:
        print(
            "WARNING: none of the core auth cookies "
            f"({', '.join(sorted(critical))}) were found — the export may "
            "have happened while signed out, or the extension may not have "
            "captured httpOnly cookies. Double-check you were actually "
            "signed in before exporting."
        )

    output_path = Path(args.output)
    output_path.write_text(
        json.dumps({"cookies": google_cookies, "origins": []}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(google_cookies)} google.com cookies to {output_path}")
    print(
        "Next: scripts/upload_google_session.py --backend-url ... --email ... --user-email ..."
    )


if __name__ == "__main__":
    main()
