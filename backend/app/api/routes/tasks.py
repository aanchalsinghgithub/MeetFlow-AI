from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.entities import Meeting
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskRead

router = APIRouter()


@router.get("", response_model=list[TaskRead])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list:
    return TaskRepository(db).list(current_user.organization_id)


@router.post("", response_model=TaskRead)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> object:
    if payload.meeting_id is not None:
        meeting = (
            db.query(Meeting)
            .filter(
                Meeting.id == payload.meeting_id,
                Meeting.organization_id == current_user.organization_id,
            )
            .one_or_none()
        )
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
    return TaskRepository(db).create(payload, current_user.organization_id)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> object:
    task = TaskRepository(db).get(task_id, current_user.organization_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
