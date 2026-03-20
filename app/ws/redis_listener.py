import json
from uuid import UUID

from app.core.redis import redis_client
from app.ws.manager import manager


async def redis_listener():

    pubsub = redis_client.pubsub()

    await pubsub.psubscribe("chat:*")

    async for message in pubsub.listen():

        if message["type"] != "pmessage":
            continue

        data = json.loads(message["data"])

        chat_id = UUID(data["chat_id"])

        await manager.broadcast(chat_id, data)