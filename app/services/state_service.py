import json
import uuid
from sqlalchemy import update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatState


async def handle_state_update(data, user_id: uuid.UUID, db: AsyncSession, redis):
    chat_id = uuid.UUID(data["chat_id"])
    delivered_seq = data.get("delivered_seq")
    read_seq = data.get("read_seq")

    values = {}

    if delivered_seq is not None:
        values["last_delivered_seq"] = func.greatest(
            ChatState.last_delivered_seq,
            delivered_seq
        )

    if read_seq is not None:
        values["last_read_seq"] = func.greatest(
            ChatState.last_read_seq,
            read_seq
        )

    if not values:
        return

    stmt = (
        update(ChatState)
        .where(
            ChatState.chat_id == chat_id,
            ChatState.user_id == user_id
        )
        .values(**values)
        .returning(
            ChatState.last_delivered_seq,
            ChatState.last_read_seq
        )
    )

    result = await db.execute(stmt)
    row = result.first()

    await db.commit()

    payload = {
        "type": "state_update",
        "chat_id": str(chat_id),
        "user_id": str(user_id),
        "delivered_seq": row[0],
        "read_seq": row[1],
    }

    # очищаем pending
    await redis.zremrangebyscore(
        f"pending:{user_id}",
        0,
        row[0]
    )

    await redis.publish(f"chat:{chat_id}", json.dumps(payload))