from celery import Celery

from app.core.config import settings

celery_app = Celery("meetflow", broker=settings.redis_url, backend=settings.redis_url)


@celery_app.task
def detect_upcoming_meetings() -> str:
    return "calendar scan queued"
