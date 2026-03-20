import time
import json

from app.core.redis import redis_client

PRESENCE_TTL = 30


async def set_user_online(user_id: str):
    # ставим ключ с TTL
    await redis_client.set(
        f"user:{user_id}:online",
        1,
        ex=PRESENCE_TTL
    )

    # уведомляем систему
    await redis_client.publish(
        "presence",
        json.dumps({
            "type": "presence",
            "user_id": user_id,
            "status": "online"
        })
    )


async def set_user_offline(user_id: str):
    # сохраняем last_seen
    await redis_client.set(
        f"user:{user_id}:last_seen",
        int(time.time())
    )

    # уведомляем систему
    await redis_client.publish(
        "presence",
        {
            "type": "presence",
            "user_id": user_id,
            "status": "offline"
        }
    )