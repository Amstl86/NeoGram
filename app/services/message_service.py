import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message
from app.services.chat_service import get_chat_members


async def handle_send_message(data, user_id: uuid.UUID, db: AsyncSession, redis):
    chat_id = uuid.UUID(data["chat_id"])
    text = data["text"].strip()
    client_id = data.get("client_id")

    if not text:
        return

    # 🔥 membership check
    is_member = await redis.sismember(f"chat:{chat_id}:members", str(user_id))
    if not is_member:
        return

    # 🔥 seq через Redis
    seq = await redis.incr(f"chat:{chat_id}:seq")

    msg = Message(
        chat_id=chat_id,
        sender_id=user_id,
        content=text,
        seq=seq,
        client_id=client_id
    )

    db.add(msg)
    await db.commit()

    payload = {
        "type": "new_message",
        "chat_id": str(chat_id),
        "seq": seq,
        "sender_id": str(user_id),
        "text": text,
        "client_id": client_id
    }

    members = await get_chat_members(chat_id, db, redis)

    # pending queue
    for uid in members:
        await redis.zadd(f"pending:{uid}", {json.dumps(payload): seq})
        await redis.expire(f"pending:{uid}", 86400)

    # await redis.publish(f"chat:{chat_id}", json.dumps(payload))
    # 🆕 сохраняем в history (для GAP recovery)
    await redis.zadd(
        f"chat:{chat_id}:history",
        {json.dumps(payload): seq}
    )

    # 🆕 ограничиваем размер (например 1000 сообщений)
    await redis.zremrangebyrank(
        f"chat:{chat_id}:history",
        0,
        -1001
    )

    # pub/sub
    await redis.publish(f"chat:{chat_id}", json.dumps(payload))