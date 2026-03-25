import json
import asyncio
import time
import uuid

from app.ws.manager import broadcast_to_user


async def retry_pending_worker(redis):
    while True:
        try:
            cursor = 0

            while True:
                cursor, keys = await redis.scan(cursor, match="pending:*", count=100)

                for key in keys:
                    user_id = uuid.UUID(key.split(":")[1])

                    messages = await redis.zrange(key, 0, -1)

                    now = time.time()

                    for raw in messages:
                        payload = json.loads(raw)

                        retry_at = payload.get("retry_at", 0)
                        retry_count = payload.get("retry_count", 0)

                        if retry_at > now:
                            continue

                        if retry_count > 5:
                            continue

                        payload["retry_at"] = now + 5
                        payload["retry_count"] = retry_count + 1

                        await broadcast_to_user(user_id, payload)

                        await redis.zadd(
                            key,
                            {json.dumps(payload): payload["seq"]}
                        )

                if cursor == 0:
                    break

            await asyncio.sleep(2)

        except Exception as e:
            print("Retry error:", e)
            await asyncio.sleep(5)