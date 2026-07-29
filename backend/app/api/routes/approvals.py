from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.entities import Approval, Meeting, Task
from app.schemas.task import ApprovalUpdate
from app.services.approval_service import ApprovalService

router = APIRouter()


@router.get("/queue")
def approval_queue(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    # BUGFIX: this used to join only Approval + Task, so the queue had no
    # idea which meeting a task came from — fine with one meeting, useless
    # once there's more than one. Outer-joining Meeting (outer, since
    # meeting_id is nullable / the meeting could've been deleted) adds that
    # context without changing anything else about the response shape.
    rows = (
        db.query(Approval, Task, Meeting)
        .join(Task, Approval.task_id == Task.id)
        .outerjoin(Meeting, Task.meeting_id == Meeting.id)
        .filter(Approval.organization_id == current_user.organization_id)
        .filter(Task.organization_id == current_user.organization_id)
        .order_by(Approval.created_at.desc())
        .all()
    )
    return [
        {
            "approval_id": approval.id,
            "task_id": task.id,
            "task": task.title,
            "owner": task.owner,
            "domain": task.domain,
            "manager_email": approval.manager_email,
            "confidence": task.confidence,
            "decision": approval.decision,
            "meeting_id": meeting.id if meeting else None,
            "meeting_title": meeting.title if meeting else "No meeting",
            "meeting_status": meeting.status if meeting else None,
        }
        for approval, task, meeting in rows
    ]


@router.post("/{task_id}/decision")
def decide(
    task_id: int,
    payload: ApprovalUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    # BUGFIX: this used to return only {"status": "updated"} even when the
    # post-approval email silently failed to send (see approval_service.py /
    # email_service.py) - there was no way to tell from the API response
    # whether the email actually went out. ApprovalService.decide() now
    # returns an email status dict; it's included here as an additive field
    # so existing frontend code that only reads `status` keeps working.
    try:
        email_status = ApprovalService(db).decide(task_id, payload, current_user.organization_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "updated", "email": email_status}
