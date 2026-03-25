import uuid
from sqlalchemy import select

from app.models import ChatMember


async def get_chat_members(chat_id, db, redis):
    key = f"chat:{chat_id}:members"

    members = await redis.smembers(key)
    if members:
        return [uuid.UUID(uid) for uid in members]

    result = await db.execute(
        select(ChatMember.user_id).where(
            ChatMember.chat_id == chat_id
        )
    )

    user_ids = [row[0] for row in result.all()]

    if user_ids:
        await redis.sadd(key, *[str(uid) for uid in user_ids])

    return user_ids