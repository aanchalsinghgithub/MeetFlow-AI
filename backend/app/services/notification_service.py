import httpx

from app.core.config import settings


class NotificationService:
    async def slack(self, text: str) -> None:
        if not settings.slack_webhook_url:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(settings.slack_webhook_url, json={"text": text})

    async def microsoft_teams(self, webhook_url: str, text: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook_url, json={"text": text})

    async def jira_ticket(self, project_key: str, summary: str, description: str) -> dict[str, str]:
        return {"project_key": project_key, "summary": summary, "description": description, "status": "stubbed"}
