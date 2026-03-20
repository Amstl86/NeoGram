from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import AsyncSessionLocal
from app.models import ChatMember, Message
from app.schemas import ChatListItem

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@router.get("/chats", response_model=list[ChatListItem])
async def get_user_chats(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):

    # subquery: последний seq сообщения в каждом чате
    last_seq_subq = (
        select(
            Message.chat_id,
            func.max(Message.seq).label("last_seq")
        )
        .group_by(Message.chat_id)
        .subquery()
    )

    # основной запрос
    query = (
        select(
            ChatMember.chat_id,
            Message.content,
            Message.seq,
            Message.created_at,
            (
                last_seq_subq.c.last_seq - ChatMember.last_read_seq
            ).label("unread_count")
        )
        .join(last_seq_subq, last_seq_subq.c.chat_id == ChatMember.chat_id)
        .join(
            Message,
            (Message.chat_id == ChatMember.chat_id)
            & (Message.seq == last_seq_subq.c.last_seq)
        )
        .where(ChatMember.user_id == user_id)
        .order_by(Message.created_at.desc())
    )

    result = await db.execute(query)

    rows = result.all()

    chats = []

    for row in rows:
        chats.append(
            ChatListItem(
                chat_id=row.chat_id,
                last_message_text=row.content,
                last_message_seq=row.seq,
                last_message_created_at=row.created_at,
                unread_count=max(row.unread_count, 0)
            )
        )

    return chats
