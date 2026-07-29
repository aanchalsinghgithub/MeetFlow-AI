from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.entities import CalendarConnection
from app.schemas.calendar import CalendarAuthURL, CalendarConnectionRead
from app.services.calendar_service import CalendarIntegrationService

router = APIRouter()


@router.get("/{provider}/upcoming")
def upcoming(provider: str, current_user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    """Legacy demo endpoint, kept for backward compatibility."""
    return CalendarIntegrationService().upcoming_meetings(provider, datetime.utcnow())


@router.get("/connect", response_model=CalendarAuthURL)
def connect(current_user: CurrentUser = Depends(get_current_user)) -> CalendarAuthURL:
    """Return the Google OAuth consent screen URL for the frontend to redirect to."""
    try:
        url = CalendarIntegrationService().get_authorization_url(
            user_id=current_user.user_id,
            organization_id=current_user.organization_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return CalendarAuthURL(authorization_url=url)


@router.get("/callback")
def callback(code: str | None = None, error: str | None = None, state: str | None = None, db: Session = Depends(get_db)) -> RedirectResponse:
    """Google OAuth redirect target: exchanges the code, stores tokens, and
    redirects back to the frontend meetings dashboard."""
    if error or not code:
        return RedirectResponse(url=f"{settings.frontend_url}/?calendar=error")

    try:
        connection = CalendarIntegrationService().exchange_code(code, state or "", db)
    except Exception:
        import traceback; traceback.print_exc()
        return RedirectResponse(url=f"{settings.frontend_url}/?calendar=error")

    CalendarIntegrationService().sync_upcoming_meetings(db, connection)
    return RedirectResponse(url=f"{settings.frontend_url}/?calendar=connected")


@router.get("/status", response_model=list[CalendarConnectionRead])
def status(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[CalendarConnectionRead]:
    """List connected Google Calendar accounts."""
    connections = (
        db.query(CalendarConnection)
        .filter(CalendarConnection.organization_id == current_user.organization_id)
        .all()
    )
    return [CalendarConnectionRead(id=c.id, user_email=c.user_email, connected=True) for c in connections]
