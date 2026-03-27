import uuid
from sqlalchemy import String, DateTime, Index, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from typing import List

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now(timezone.utc)
    )

    last_seen: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now(timezone.utc)
    )

class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    title: Mapped[str | None] = mapped_column(String, nullable=True)

    # is_group: Mapped[bool] = mapped_column(Boolean, default=False)
    type: Mapped[str] = mapped_column(
        String,
        default="private"  # private | group
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now(timezone.utc)
    )

    members: Mapped[List["ChatMember"]] = relationship(
        back_populates="chat",
        cascade="all, delete"
    )


class ChatMember(Base):
    __tablename__ = "chat_members"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id"),
        Index("ix_chat_members_chat_user", "chat_id", "user_id"),
        Index("ix_chat_members_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String,
        default="member"
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id"),
        nullable=False
    )

    last_read_seq: Mapped[int] = mapped_column(
        default=0,
        nullable=False
    )

    last_delivered_seq: Mapped[int] = mapped_column(
        default=0,
        nullable=False
    )

    chat: Mapped["Chat"] = relationship(
        back_populates="members"
    )



class Message(Base):
    __tablename__ = "messages"

    __table_args__ = (
        Index("ix_messages_chat_seq", "chat_id", "seq"),
        UniqueConstraint("chat_id", "seq"),  # защита порядка
        UniqueConstraint("chat_id", "sender_id", "client_id"),  # дедуп
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id"),
        index=True
    )

    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True
    )

    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    # ключ для offline dedup
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True
    )

    content: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )
    attachments: Mapped[List["Attachment"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan"
    )


class Attachment(Base):
    __tablename__ = "attachments"

    __table_args__ = (
        Index("ix_attachments_message_id", "message_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False
    )

    file_name: Mapped[str] = mapped_column(String, nullable=False)

    file_type: Mapped[str] = mapped_column(
        String,
        nullable=False  # image / video / file
    )

    mime_type: Mapped[str] = mapped_column(String, nullable=False)

    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    # storage layer
    storage: Mapped[str] = mapped_column(
        String,
        nullable=False  # local / s3
    )

    path: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    url: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now(timezone.utc)
    )

    message: Mapped["Message"] = relationship(
        back_populates="attachments"
    )

class ChatState(Base):
    __tablename__ = "chat_states"

    __table_args__ = (
        UniqueConstraint("user_id", "chat_id"),  # 🔥 один state на пользователя в чате
        Index("ix_chat_states_user_chat", "user_id", "chat_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        primary_key=True
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id"),
        primary_key=True
    )

    # 🔥 до какого seq доставлено
    last_delivered_seq: Mapped[int] = mapped_column(
        default=0,
        nullable=False
    )

    # 🔥 до какого seq прочитано
    last_read_seq: Mapped[int] = mapped_column(
        default=0,
        nullable=False
    )
