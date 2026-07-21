from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.enums import MeetingProvider


class TranscriptTurn(BaseModel):
    speaker: str
    text: str
    timestamp: str | None = None


class MeetingCreate(BaseModel):
    title: str
    provider: MeetingProvider = MeetingProvider.GOOGLE_MEET
    external_id: str | None = None
    join_url: str | None = None
    starts_at: datetime | None = None
    participants: list[str] = []


# ---------------------------------------------------------------------------
# BUGFIX (ResponseValidationError on GET /api/meetings/{id}):
#
# MeetingRead used to declare `risks: list[str]` / `blockers: list[str]`, but
# the AI (mistral_service.summarize_meeting) now returns structured objects:
#
#   risks    = [{"risk": "...", "impact": "...", "mitigation": "..."}]
#   blockers = [{"blocker": "...", "impact": "...", "owner": "...", "action": "..."}]
#
# FastAPI validates the ORM object against the response_model on the way
# OUT, so as soon as a meeting had structured risks/blockers in its JSON
# column, `list[str]` rejected every dict item and the endpoint 500'd with
# ResponseValidationError - even though the row was saved successfully.
#
# Fix: give risks/blockers their own models, and accept EITHER a plain
# string (old rows, or the LLM fallback summary which still emits strings)
# OR a structured dict (new rows) via a `mode="before"` validator that
# normalizes a bare string into {"risk": "<string>"} / {"blocker": "<string>"}
# before field validation runs. This is backwards compatible with every
# meeting already in the database and forwards compatible with the new
# structured shape - no data migration required.
# ---------------------------------------------------------------------------
class RiskItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    risk: str = ""
    impact: str | None = None
    mitigation: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, value):
        if isinstance(value, str):
            return {"risk": value}
        if isinstance(value, dict):
            return value
        return {"risk": str(value)}


class BlockerItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    blocker: str = ""
    impact: str | None = None
    owner: str | None = None
    action: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, value):
        if isinstance(value, str):
            return {"blocker": value}
        if isinstance(value, dict):
            return value
        return {"blocker": str(value)}


class MeetingRead(BaseModel):
    id: int
    title: str
    provider: str
    join_url: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    summary: str | None = None
    decisions: list[str] = []
    key_discussion_points: list[str] = []
    risks: list[RiskItem] = []
    blockers: list[BlockerItem] = []
    transcript: list[dict] = []

    class Config:
        from_attributes = True


class MeetingDetail(MeetingRead):
    participants: list[str] = []
    task_count: int = 0


class ProcessTranscriptRequest(BaseModel):
    meeting_id: int | None = None
    meeting_title: str = "Ad hoc meeting"
    participants: list[str] = []
    transcript: list[TranscriptTurn]


class ProcessTranscriptResponse(BaseModel):
    meeting: MeetingRead
    tasks: list["TaskRead"]


from app.schemas.task import TaskRead

ProcessTranscriptResponse.model_rebuild()
