from datetime import datetime

from pydantic import BaseModel


class CalendarConnectionRead(BaseModel):
    id: int
    user_email: str
    connected: bool = True

    class Config:
        from_attributes = True


class CalendarAuthURL(BaseModel):
    authorization_url: str


class UpcomingMeetingRead(BaseModel):
    id: int
    title: str
    provider: str
    join_url: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: str
    participants: list[str] = []

    class Config:
        from_attributes = True


class MeetingStatusRead(BaseModel):
    id: int
    status: str
    title: str

    class Config:
        from_attributes = True


class TranscriptEntryRead(BaseModel):
    id: int
    speaker: str
    text: str
    timestamp: str | None = None

    class Config:
        from_attributes = True


class TranscriptResponse(BaseModel):
    meeting_id: int
    status: str
    entries: list[TranscriptEntryRead]
