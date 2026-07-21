from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskRead

router = APIRouter()


@router.get("", response_model=list[TaskRead])
def list_tasks(db: Session = Depends(get_db)) -> list:
    return TaskRepository(db).list()


@router.post("", response_model=TaskRead)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> object:
    return TaskRepository(db).create(payload)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, db: Session = Depends(get_db)) -> object:
    task = TaskRepository(db).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
