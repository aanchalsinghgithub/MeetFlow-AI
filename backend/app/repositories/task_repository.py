from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Approval, Task
from app.schemas.task import TaskCreate


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: TaskCreate) -> Task:
        task = Task(
            meeting_id=payload.meeting_id,
            title=payload.title,
            description=payload.description,
            owner=payload.owner,
            mentioned_by=payload.mentioned_by,
            requested_by=payload.requested_by,
            priority=payload.priority.value,
            deadline=payload.deadline,
            domain=payload.domain,
            dependencies=payload.dependencies,
            confidence=payload.confidence,
            status=payload.status.value,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def list(self) -> list[Task]:
        return list(self.db.scalars(select(Task).order_by(Task.created_at.desc())))

    def get(self, task_id: int) -> Task | None:
        return self.db.get(Task, task_id)

    def add_approval(self, task_id: int, manager_email: str) -> Approval:
        approval = Approval(task_id=task_id, manager_email=manager_email)
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def latest_approval(self, task_id: int) -> Approval | None:
        return self.db.scalars(
            select(Approval)
            .where(Approval.task_id == task_id)
            .order_by(Approval.created_at.desc())
            .limit(1)
        ).first()
