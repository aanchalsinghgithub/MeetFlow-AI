import json
from typing import Any

import httpx

from app.core.config import settings


class MistralService:
    def __init__(self, model: str = "mistral-small") -> None:
        self.model = model
        self.api_key = settings.mistral_api_key

    async def extract_json(self, prompt: str) -> list[dict[str, Any]]:
        if not self.api_key:
            return []

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only valid JSON: a single JSON object of the shape "
                        '{"tasks": [...]}. Each item in "tasks" is an action item with '
                        "owner and context. If there are no action items, return {\"tasks\": []}."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, KeyError, IndexError):
            return []
        return parsed if isinstance(parsed, list) else parsed.get("tasks", [])

    async def summarize_meeting(self, transcript: str) -> dict[str, Any]:
        if not self.api_key:
            return self._fallback_summary(transcript)

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return valid JSON with keys executive_summary, key_discussion_points, "
                        "decisions_taken, risks, and blockers.\n"
                        "executive_summary: a short paragraph (string).\n"
                        "key_discussion_points: an array of strings.\n"
                        "decisions_taken: an array of strings.\n"
                        "risks: an array of objects, each shaped exactly as "
                        '{"risk": "<what the risk is>", "impact": "<what happens if it '
                        'materializes>", "mitigation": "<how to reduce/handle it>"}.\n'
                        "blockers: an array of objects, each shaped exactly as "
                        '{"blocker": "<what is blocking progress>", "impact": "<what it '
                        'is blocking>", "owner": "<who can unblock it>", "action": '
                        '"<the next step to clear it>"}.\n'
                        "If there are no risks or blockers, return empty arrays for them. "
                        "Do not return risks or blockers as plain strings - always use the "
                        "object shape described above."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, KeyError, IndexError):
            return self._fallback_summary(transcript)
        return parsed if isinstance(parsed, dict) else self._fallback_summary(transcript)

    @staticmethod
    def _fallback_summary(transcript: str) -> dict[str, Any]:
        lines = [line.strip() for line in transcript.splitlines() if line.strip()]
        highlights = lines[:5]
        decisions = [
            line
            for line in lines
            if any(word in line.lower() for word in ["decided", "approved", "will", "should", "need"])
        ][:4]
        # NOTE: these are plain strings (no API key configured, so this is a
        # best-effort local fallback, not an LLM call). The response schema
        # (app/schemas/meeting.py::RiskItem/BlockerItem) accepts plain
        # strings as well as the structured {risk/impact/mitigation} and
        # {blocker/impact/owner/action} shapes, so this fallback still
        # round-trips through GET /api/meetings/{id} without a 500.
        return {
            "executive_summary": "The meeting produced action items that need manager review before assignment.",
            "key_discussion_points": highlights,
            "decisions_taken": decisions,
            "risks": ["Review extracted owners and deadlines before approval."],
            "blockers": [],
        }
