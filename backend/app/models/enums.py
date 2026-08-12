from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"


class MeetingProvider(StrEnum):
    GOOGLE_MEET = "google_meet"
    MICROSOFT_TEAMS = "microsoft_teams"
    ZOOM = "zoom"


class MeetingStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(StrEnum):
    DRAFT = "draft"
    REVIEW_REQUIRED = "review_required"
    AUTO_APPROVE_CANDIDATE = "auto_approve_candidate"
    APPROVED = "approved"
    REJECTED = "rejected"
    ASSIGNED = "assigned"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ApprovalDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
