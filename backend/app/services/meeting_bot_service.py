from app.services.meeting_bot import MeetingBot


class MeetingBotService:
    """Thin facade used by API routes / the scheduler to launch a MeetingBot.

    Kept as a separate service (rather than calling MeetingBot directly from
    routes) to preserve the existing API surface used by
    ``POST /meetings/{id}/join-bot``.
    """

    def join(self, provider: str, join_url: str, meeting_id: int | None = None) -> dict[str, str]:
        if not join_url:
            return {
                "provider": provider,
                "join_url": join_url,
                "status": "failed",
                "note": "Meeting has no join URL.",
            }

        if meeting_id is not None:
            MeetingBot(meeting_id=meeting_id, join_url=join_url).start_async()
            return {
                "provider": provider,
                "join_url": join_url,
                "status": "bot_joining",
                "note": "MeetFlow bot is launching in the background.",
            }

        return {
            "provider": provider,
            "join_url": join_url,
            "status": "scheduled_for_bot_join",
            "note": "Production adapter should use approved bot accounts and provider APIs.",
        }
