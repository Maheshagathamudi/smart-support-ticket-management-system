from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import (
    Ticket,
    TicketHistory,
    Notification,
    Priority,
    TicketStatus,
)


@celery_app.task(name="app.tasks.sla.check_sla")
def check_sla():
    targets = {
        Priority.HIGH: settings.resolution_high_minutes,
        Priority.CRITICAL: settings.resolution_critical_minutes,
    }
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        rows = db.scalars(
            select(Ticket).where(
                Ticket.status.not_in([TicketStatus.RESOLVED, TicketStatus.CLOSED])
            )
        ).all()
        for ticket in rows:
            minutes = targets.get(ticket.priority)
            if minutes is None or ticket.created_at > now - timedelta(minutes=minutes):
                continue
            existing = db.scalar(
                select(TicketHistory).where(
                    TicketHistory.ticket_id == ticket.id,
                    TicketHistory.event_type == "sla_breach",
                )
            )
            if existing:
                continue
            db.add(
                TicketHistory(
                    ticket_id=ticket.id,
                    actor_id=ticket.creator_id,
                    event_type="sla_breach",
                    new_value=f"resolution>{minutes}m",
                )
            )
            if ticket.assigned_agent_id:
                db.add(
                    Notification(
                        user_id=ticket.assigned_agent_id,
                        ticket_id=ticket.id,
                        message=f"SLA breach: ticket #{ticket.id} is overdue",
                    )
                )
        db.commit()
