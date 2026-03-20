from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import AsyncSessionLocal
from app.models import Message
from app.schemas import MessageOut

router = APIRouter()

# функция зависимости для FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def get_messages(
    chat_id: UUID,
    limit: int = Query(50, le=100),         # макс 100 сообщений за один запрос
    before_seq: int | None = None,          # курсор пагинации
    db: AsyncSession = Depends(get_db)
):
    """
    Получение истории сообщений для чата.
    - limit: количество сообщений
    - before_seq: загружать сообщения с seq < before_seq
    """
    query = select(Message).where(Message.chat_id == chat_id)

    if before_seq is not None:
        query = query.where(Message.seq < before_seq)

    query = query.order_by(Message.seq.desc()).limit(limit)

    result = await db.execute(query)
    messages = result.scalars().all()

    # возвращаем от старых к новым
    return list(reversed(messages))