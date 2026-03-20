from uuid import UUID

from sqlalchemy import select, func

from app.core.redis import redis_client
from app.database import AsyncSessionLocal
from app.models import Message


async def get_next_seq(chat_id: UUID) -> int:
    key = f"chat:{chat_id}:seq"

    # проверяем, есть ли счетчик в Redis
    exists = await redis_client.exists(key)

    if not exists:
        # синхронизация с БД (один раз)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(func.max(Message.seq)).where(
                    Message.chat_id == chat_id
                )
            )
            max_seq = result.scalar() or 0

        await redis_client.set(key, max_seq)

    # атомарное увеличение
    return await redis_client.incr(key)