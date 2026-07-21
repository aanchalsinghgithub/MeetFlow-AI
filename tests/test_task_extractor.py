import pytest

from app.schemas.meeting import TranscriptTurn
from app.services.task_extractor import TaskExtractor


@pytest.mark.asyncio
async def test_extracts_owner_context_deadline_and_domain() -> None:
    transcript = [
        TranscriptTurn(speaker="Ajay", text="I'll update the login page by Friday."),
        TranscriptTurn(speaker="Rahul", text="Priya should fix the API timeout issue."),
        TranscriptTurn(speaker="Client", text="We need dashboard filters fixed before next week's demo."),
    ]

    tasks = await TaskExtractor().extract(transcript)

    assert len(tasks) == 3
    assert tasks[0].title == "Update the login page"
    assert tasks[0].owner == "Ajay"
    assert tasks[0].mentioned_by == "Ajay"
    assert tasks[0].deadline == "Friday"
    assert tasks[0].domain == "Frontend"

    assert tasks[1].owner == "Priya"
    assert tasks[1].domain == "Backend"

    assert tasks[2].requested_by == "Client"
    assert tasks[2].priority.value == "high"
    assert tasks[2].domain == "Frontend"
