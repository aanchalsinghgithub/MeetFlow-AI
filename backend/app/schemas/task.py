from pydantic import BaseModel, Field

from app.models.enums import Priority, TaskStatus


class ExtractedTask(BaseModel):
    task: str
    description: str | None = None
    owner: str | None = None
    mentioned_by: str | None = None
    requested_by: str | None = None
    priority: Priority = Priority.MEDIUM
    deadline: str | None = None
    domain: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)


class TaskCreate(BaseModel):
    meeting_id: int | None = None
    title: str
    description: str | None = None
    owner: str | None = None
    mentioned_by: str | None = None
    requested_by: str | None = None
    priority: Priority = Priority.MEDIUM
    deadline: str | None = None
    domain: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    status: TaskStatus = TaskStatus.REVIEW_REQUIRED


class TaskRead(TaskCreate):
    id: int

    class Config:
        from_attributes = True


class ApprovalUpdate(BaseModel):
    decision: str
    edited_task: TaskCreate | None = None
    notes: str | None = None
    # NEW: lets the Approval Queue UI override where the post-approval
    # "task assigned" email is sent, per-task, instead of always using the
    # hardcoded test recipient. Optional - if omitted/blank,
    # ApprovalService.decide() falls back to _TASK_ASSIGNMENT_TEST_EMAIL.
    recipient_email: str | None = None
