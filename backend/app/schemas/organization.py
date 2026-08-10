from pydantic import BaseModel


class GoogleBotSessionUpload(BaseModel):
    email: str
    # Playwright's context.storage_state(path=...) output, loaded as JSON
    # and posted here as-is (see scripts/upload_google_session.py).
    storage_state: dict


class GoogleBotSessionStatus(BaseModel):
    configured: bool
    email: str | None = None
