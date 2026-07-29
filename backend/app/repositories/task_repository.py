from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Approval, Task
from app.schemas.task import TaskCreate


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: TaskCreate, organization_id: int) -> Task:
        task = Task(
            organization_id=organization_id,
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

    def list(self, organization_id: int) -> list[Task]:
        return list(
            self.db.scalars(
                select(Task)
                .where(Task.organization_id == organization_id)
                .order_by(Task.created_at.desc())
            )
        )

    def get(self, task_id: int, organization_id: int | None = None) -> Task | None:
        query = select(Task).where(Task.id == task_id)
        if organization_id is not None:
            query = query.where(Task.organization_id == organization_id)
        return self.db.scalars(query).first()

    def add_approval(self, task_id: int, manager_email: str, organization_id: int) -> Approval:
        approval = Approval(
            organization_id=organization_id,
            task_id=task_id,
            manager_email=manager_email,
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def latest_approval(self, task_id: int, organization_id: int | None = None) -> Approval | None:
        query = select(Approval).where(Approval.task_id == task_id)
        if organization_id is not None:
            query = query.where(Approval.organization_id == organization_id)
        return self.db.scalars(
            query
            .order_by(Approval.created_at.desc())
            .limit(1)
        ).first()
