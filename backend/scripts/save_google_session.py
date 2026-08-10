"""DEPRECATED — replaced by scripts/convert_cookies.py.

This script (and the "open a real, already-authenticated Chrome profile
via Playwright" approach it used) doesn't work: Google detects that the
browser is CDP-controlled — which is fundamental to how Playwright,
Selenium, and Puppeteer all work, no matter the channel, profile, or
headless setting — and blocks "Couldn't sign you in" on ANY visit to a
Google-owned page, not just the login form. There's no Playwright-based
fix for this.

Use scripts/convert_cookies.py instead: export cookies from a completely
normal, manually-used Chrome session via a browser extension (which reads
them through Chrome's own internal API, so nothing about it looks like
automation to Google), then convert that export to the JSON format the
bot needs. See that script's docstring for the full steps.
"""

raise SystemExit(
    "This script is deprecated and won't work against Google's automation "
    "detection. Use scripts/convert_cookies.py instead — see its docstring "
    "for the (non-Playwright) steps."
)
