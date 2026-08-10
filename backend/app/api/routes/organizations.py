import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.entities import Organization
from app.schemas.organization import GoogleBotSessionStatus, GoogleBotSessionUpload

router = APIRouter()

CRITICAL_AUTH_COOKIES = {"SID", "HSID", "SSID", "__Secure-1PSID", "__Secure-3PSID"}


def _get_org(db: Session, organization_id: int) -> Organization:
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _parse_netscape_cookies(text: str) -> list[dict]:
    """Same format/logic as scripts/convert_cookies.py.

    Deliberately duplicated rather than imported: this script is meant to
    be run standalone by anyone, without the rest of the app package on
    their PYTHONPATH, so it can't depend on importing from `app`. Keeping
    both copies small and side-by-side is simpler than fighting import
    paths for a ~20-line parser. If this ever needs a third home, pull it
    into a shared module instead.
    """
    cookies = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        http_only = False
        if line.startswith("#HttpOnly_"):
            http_only = True
            line = line[len("#HttpOnly_"):]
        elif line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) != 7:
            continue

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
                "sameSite": "Lax",
            }
        )
    return cookies


@router.get("/google-bot-session", response_model=GoogleBotSessionStatus)
def get_google_bot_session_status(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Whether this org has its own bot Google session configured.

    Deliberately never returns the stored storage_state itself — it's live
    session cookies, no reason for it to round-trip back over the API once
    it's saved.
    """
    org = _get_org(db, current_user.organization_id)
    return GoogleBotSessionStatus(
        configured=bool(org.google_bot_storage_state),
        email=org.google_bot_email,
    )


@router.post("/google-bot-session", response_model=GoogleBotSessionStatus)
def set_google_bot_session(
    payload: GoogleBotSessionUpload,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Store this org's own bot Google session from a pre-converted
    storage_state JSON payload — used by scripts/upload_google_session.py.

    Prefer POST /google-bot-session/upload-cookies-file for anything
    UI-facing — it takes the raw cookies.txt export directly and needs no
    local Python/terminal step. This JSON version stays for scripting /
    CI-style use.
    """
    org = _get_org(db, current_user.organization_id)
    org.google_bot_email = payload.email
    org.google_bot_storage_state = json.dumps(payload.storage_state)
    db.commit()
    db.refresh(org)
    return GoogleBotSessionStatus(configured=True, email=org.google_bot_email)


@router.post("/google-bot-session/upload-cookies-file", response_model=GoogleBotSessionStatus)
async def upload_google_bot_cookies_file(
    email: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """UI-facing version of the endpoint above: takes the raw cookies.txt
    (Netscape format) exported by a browser extension directly, parses it
    server-side, and stores it against the caller's organization.

    This is what makes the bot-account setup usable by an actual tenant
    admin instead of only someone with the codebase — no terminal, no
    Python, no scripts/*.py on their end. They just export a file from
    their browser and upload it on a settings page (see
    frontend/src/components/BotAccountSettings.tsx).
    """
    raw = (await file.read()).decode("utf-8", errors="replace")
    cookies = _parse_netscape_cookies(raw)
    google_cookies = [c for c in cookies if "google.com" in c["domain"]]

    if not google_cookies:
        raise HTTPException(
            status_code=400,
            detail=(
                "No google.com cookies found in that file. Make sure you "
                "were signed in to the bot's Google account when you "
                "exported it."
            ),
        )

    found_critical = {c["name"] for c in google_cookies} & CRITICAL_AUTH_COOKIES
    if not found_critical:
        raise HTTPException(
            status_code=400,
            detail=(
                "That file doesn't contain any of the core Google sign-in "
                "cookies (SID/HSID/SSID/etc) — it looks like you weren't "
                "actually signed in when you exported. Sign in, then "
                "export again."
            ),
        )

    org = _get_org(db, current_user.organization_id)
    org.google_bot_email = email
    org.google_bot_storage_state = json.dumps({"cookies": google_cookies, "origins": []})
    db.commit()
    db.refresh(org)
    return GoogleBotSessionStatus(configured=True, email=org.google_bot_email)


@router.delete("/google-bot-session", response_model=GoogleBotSessionStatus)
def clear_google_bot_session(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Clear this org's bot session — e.g. once it's expired, or to fall
    back to the anonymous-guest join while you regenerate a new one."""
    org = _get_org(db, current_user.organization_id)
    org.google_bot_email = None
    org.google_bot_storage_state = None
    db.commit()
    return GoogleBotSessionStatus(configured=False, email=None)
