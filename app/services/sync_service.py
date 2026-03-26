import json

from sqlalchemy import select, update
from app.models import Message, ChatState


async def get_messages_after_f(db, chat_id, from_seq, limit=100):
    result = await db.execute(
        select(Message)
        .where(
            Message.chat_id == chat_id,
            Message.seq > from_seq
        )
        .order_by(Message.seq)
        .limit(limit)
    )

    return result.scalars().all()


async def sync_chat(db, user_id, chat_id, last_seen):
    result = await db.execute(
        select(Message)
        .where(
            Message.chat_id == chat_id,
            Message.seq > last_seen
        )
        .order_by(Message.seq)
        .limit(1000)
    )

    messages = result.scalars().all()

    if messages:
        max_seq = messages[-1].seq

        await db.execute(
            update(ChatState)
            .where(
                ChatState.user_id == user_id,
                ChatState.chat_id == chat_id
            )
            .values(last_delivered_seq=max_seq)
        )

    return messages

# Redis-first recovery
async def get_messages_after(redis, db, chat_id, from_seq, limit=100):
    """
    Сначала пробуем Redis, потом fallback в БД
    """

    # 🔥 1. пробуем Redis
    redis_key = f"chat:{chat_id}:history"

    cached = await redis.zrangebyscore(
        redis_key,
        from_seq + 1,
        "+inf",
        start=0,
        num=limit
    )

    if cached:
        return [json.loads(m) for m in cached]

    # 🔥 2. fallback → DB
    result = await db.execute(
        select(Message)
        .where(
            Message.chat_id == chat_id,
            Message.seq > from_seq
        )
        .order_by(Message.seq)
        .limit(limit)
    )

    messages = result.scalars().all()

    return [
        {
            "type": "message",
            "chat_id": str(m.chat_id),
            "seq": m.seq,
            "sender_id": str(m.sender_id),
            "text": m.content,
        }
        for m in messages
    ]

