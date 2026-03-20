from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChatCreate(BaseModel):
    user_id: UUID


class ChatResponse(BaseModel):
    id: UUID

class MessageOut(BaseModel):
    id: UUID
    chat_id: UUID
    user_id: UUID
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatListItem(BaseModel):
    chat_id: UUID
    last_message_text: str | None
    last_message_seq: int | None
    last_message_created_at: datetime | None
    unread_count: int