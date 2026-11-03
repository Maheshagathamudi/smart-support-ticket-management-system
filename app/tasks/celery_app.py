from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "support",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.sla"],
)
celery_app.conf.beat_schedule = {
    "check-sla-every-5-minutes": {"task": "app.tasks.sla.check_sla", "schedule": 300.0}
}
celery_app.autodiscover_tasks(["app.tasks"])
