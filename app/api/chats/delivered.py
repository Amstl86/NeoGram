from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import AsyncSessionLocal
from app.models import ChatMember

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/chats/{chat_id}/delivered")
async def mark_delivered(
    chat_id: UUID,
    seq: int,
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):

    await db.execute(
        update(ChatMember)
        .where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == user_id
        )
        .values(last_delivered_seq=seq)
    )

    await db.commit()

    return {"status": "ok"}