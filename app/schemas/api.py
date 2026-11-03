from pydantic import BaseModel, EmailStr, Field
from app.models.entities import Role, TicketStatus, Priority


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TicketIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1)
    priority: Priority = Priority.MEDIUM


class TicketPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    status: TicketStatus | None = None
    priority: Priority | None = None


class TicketOut(BaseModel):
    id: int
    title: str
    description: str
    status: TicketStatus
    priority: Priority
    creator_id: int
    assigned_agent_id: int | None
    created_at: object
    updated_at: object


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class CommentOut(BaseModel):
    id: int
    ticket_id: int
    author_id: int
    body: str
    created_at: object
