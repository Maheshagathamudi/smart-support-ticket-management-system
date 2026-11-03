from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.db.session import Base, engine, get_db
from app.models.entities import (
    User,
    Ticket,
    Comment,
    TicketHistory,
    Notification,
    Role,
    TicketStatus,
)
from app.schemas.api import (
    RegisterIn,
    UserOut,
    TokenOut,
    TicketIn,
    TicketPatch,
    TicketOut,
    CommentIn,
    CommentOut,
)
from app.api.deps import current_user, require_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment != "development" and (
        len(settings.secret_key) < 32
        or settings.secret_key == "development-only-change-me"
    ):
        raise RuntimeError(
            "Set a strong SECRET_KEY of at least 32 characters outside development."
        )
    if settings.environment == "development":
        Base.metadata.create_all(engine)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/assets", StaticFiles(directory=frontend_dir), name="assets")

@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(frontend_dir / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/auth/register", response_model=UserOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(409, "Email already registered")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=Role.CUSTOMER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/api/v1/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username))
    if (
        not user
        or not user.is_active
        or not verify_password(form.password, user.password_hash)
    ):
        raise HTTPException(401, "Incorrect email or password")
    return TokenOut(access_token=create_access_token(str(user.id)))


@app.get("/api/v1/users/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@app.post("/api/v1/tickets", response_model=TicketOut, status_code=201)
def create_ticket(
    payload: TicketIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    ticket = Ticket(**payload.model_dump(), creator_id=user.id)
    db.add(ticket)
    db.flush()
    db.add(
        TicketHistory(
            ticket_id=ticket.id,
            actor_id=user.id,
            event_type="created",
            new_value=ticket.status.value,
        )
    )
    db.commit()
    db.refresh(ticket)
    return ticket


@app.get("/api/v1/tickets", response_model=list[TicketOut])
def list_tickets(
    status: TicketStatus | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    q = select(Ticket)
    if user.role == Role.CUSTOMER:
        q = q.where(Ticket.creator_id == user.id)
    elif user.role == Role.AGENT:
        q = q.where(Ticket.assigned_agent_id == user.id)
    if status:
        q = q.where(Ticket.status == status)
    return list(
        db.scalars(q.order_by(Ticket.created_at.desc()).offset(offset).limit(limit))
    )


def authorized_ticket(ticket_id: int, db: Session, user: User):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if user.role == Role.CUSTOMER and ticket.creator_id != user.id:
        raise HTTPException(404, "Ticket not found")
    if user.role == Role.AGENT and ticket.assigned_agent_id != user.id:
        raise HTTPException(404, "Ticket not found")
    return ticket


@app.get("/api/v1/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return authorized_ticket(ticket_id, db, user)


@app.patch("/api/v1/tickets/{ticket_id}", response_model=TicketOut)
def patch_ticket(
    ticket_id: int,
    payload: TicketPatch,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    ticket = authorized_ticket(ticket_id, db, user)
    if user.role == Role.CUSTOMER and any(
        k in payload.model_fields_set for k in ("status", "priority")
    ):
        raise HTTPException(403, "Customers cannot change status or priority")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        allowed = {
            TicketStatus.OPEN: {TicketStatus.IN_PROGRESS, TicketStatus.CLOSED},
            TicketStatus.IN_PROGRESS: {
                TicketStatus.PENDING,
                TicketStatus.RESOLVED,
                TicketStatus.OPEN,
            },
            TicketStatus.PENDING: {
                TicketStatus.IN_PROGRESS,
                TicketStatus.RESOLVED,
                TicketStatus.CLOSED,
            },
            TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.OPEN},
            TicketStatus.CLOSED: set(),
        }
        new = data["status"]
        if new != ticket.status and new not in allowed[ticket.status]:
            raise HTTPException(422, "Invalid status transition")
        if new != ticket.status:
            db.add(
                TicketHistory(
                    ticket_id=ticket.id,
                    actor_id=user.id,
                    event_type="status_changed",
                    old_value=ticket.status.value,
                    new_value=new.value,
                )
            )
        if new == TicketStatus.RESOLVED:
            ticket.resolved_at = datetime.now(timezone.utc)
    for key, value in data.items():
        setattr(ticket, key, value)
    db.commit()
    db.refresh(ticket)
    return ticket


@app.post("/api/v1/tickets/{ticket_id}/assign", response_model=TicketOut)
def assign(
    ticket_id: int,
    agent_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    ticket = db.get(Ticket, ticket_id)
    agent = db.get(User, agent_id) if agent_id is not None else None
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if agent_id is not None and (
        not agent or agent.role != Role.AGENT or not agent.is_active
    ):
        raise HTTPException(422, "Active agent required")
    old = ticket.assigned_agent_id
    ticket.assigned_agent_id = agent.id if agent else None
    db.add(
        TicketHistory(
            ticket_id=ticket.id,
            actor_id=user.id,
            event_type="assigned" if agent else "unassigned",
            old_value=str(old) if old else None,
            new_value=str(agent.id) if agent else None,
        )
    )
    if agent:
        db.add(
            Notification(
                user_id=agent.id,
                ticket_id=ticket.id,
                message=f"Ticket #{ticket.id} assigned",
            )
        )
    db.commit()
    db.refresh(ticket)
    return ticket


@app.post(
    "/api/v1/tickets/{ticket_id}/comments", response_model=CommentOut, status_code=201
)
def comment(
    ticket_id: int,
    payload: CommentIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    ticket = authorized_ticket(ticket_id, db, user)
    item = Comment(ticket_id=ticket.id, author_id=user.id, body=payload.body)
    db.add(item)
    db.flush()
    recipient = (
        ticket.creator_id if ticket.creator_id != user.id else ticket.assigned_agent_id
    )
    if recipient:
        db.add(
            Notification(
                user_id=recipient,
                ticket_id=ticket.id,
                message=f"New comment on ticket #{ticket.id}",
            )
        )
    db.commit()
    db.refresh(item)
    return item


@app.get("/api/v1/tickets/{ticket_id}/comments", response_model=list[CommentOut])
def comments(
    ticket_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    authorized_ticket(ticket_id, db, user)
    return list(
        db.scalars(
            select(Comment)
            .where(Comment.ticket_id == ticket_id)
            .order_by(Comment.created_at)
        )
    )


@app.get("/api/v1/tickets/{ticket_id}/history")
def history(
    ticket_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    authorized_ticket(ticket_id, db, user)
    return list(
        db.scalars(
            select(TicketHistory)
            .where(TicketHistory.ticket_id == ticket_id)
            .order_by(TicketHistory.created_at)
        )
    )


@app.get("/api/v1/notifications")
def notifications(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
        )
    )


@app.patch("/api/v1/notifications/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    item = db.get(Notification, notification_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    item.is_read = True
    db.commit()
    return {"id": item.id, "is_read": True}


@app.get("/api/v1/reports/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    status_rows = db.execute(
        select(Ticket.status, func.count()).group_by(Ticket.status)
    ).all()
    priority_rows = db.execute(
        select(Ticket.priority, func.count()).group_by(Ticket.priority)
    ).all()
    return {
        "total": db.scalar(select(func.count()).select_from(Ticket)) or 0,
        "by_status": {status.value: count for status, count in status_rows},
        "by_priority": {priority.value: count for priority, count in priority_rows},
    }


@app.get("/api/v1/reports/agents")
def agent_report(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    rows = db.execute(
        select(User.id, User.full_name, User.is_active, func.count(Ticket.id))
        .select_from(User)
        .outerjoin(Ticket, Ticket.assigned_agent_id == User.id)
        .where(User.role == Role.AGENT)
        .group_by(User.id, User.full_name, User.is_active)
        .order_by(func.count(Ticket.id).desc(), User.full_name)
    ).all()
    return [
        {
            "agent_id": agent_id,
            "agent_name": full_name,
            "is_active": is_active,
            "ticket_count": ticket_count,
        }
        for agent_id, full_name, is_active, ticket_count in rows
    ]


@app.post("/api/v1/users/agents", response_model=UserOut, status_code=201)
def create_agent(
    payload: RegisterIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(409, "Email already registered")
    agent = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=Role.AGENT,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@app.patch("/api/v1/users/{user_id}/activation", response_model=UserOut)
def set_user_activation(
    user_id: int,
    active: bool,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == admin.id and not active:
        raise HTTPException(422, "Administrators cannot deactivate their own account")
    target.is_active = active
    db.commit()
    db.refresh(target)
    return target


@app.get("/api/v1/reports/sla")
def sla_report(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    breaches = (
        db.scalar(
            select(func.count())
            .select_from(TicketHistory)
            .where(TicketHistory.event_type == "sla_breach")
        )
        or 0
    )
    return {"sla_breaches": breaches}
