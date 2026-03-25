import json
from app.ws.manager import broadcast_to_user
from app.services.chat_service import get_chat_members


async def redis_listener(db, redis):
    pubsub = redis.pubsub()
    await pubsub.psubscribe("chat:*")

    async for msg in pubsub.listen():
        if msg["type"] != "pmessage":
            continue

        data = json.loads(msg["data"])
        chat_id = data["chat_id"]

        users = await get_chat_members(chat_id, db, redis)

        for uid in users:
            await broadcast_to_user(uid, data)