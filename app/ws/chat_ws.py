import asyncio
import json
import time
from uuid import UUID

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message
from app.database import AsyncSessionLocal
from app.core.redis import redis_client
from app.core.sequence import get_next_seq
from app.core.presence import set_user_online, set_user_offline


typing_throttle: dict[str, float] = {}


async def safe_send(websocket: WebSocket, data: dict):
    try:
        await websocket.send_json(data)
    except RuntimeError:
        pass
    except ValueError:
        pass


async def chat_ws(websocket: WebSocket, user_id: UUID):
    await websocket.accept()

    # пользователь онлайн
    await set_user_online(str(user_id))

    pubsub = redis_client.pubsub()
    chat_id: UUID | None = None

    async with AsyncSessionLocal() as db:  # type: AsyncSession
        try:
            while True:
                done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(websocket.receive_text()),
                        asyncio.create_task(pubsub.get_message(ignore_subscribe_messages=True)),
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in done:
                    result = task.result()

                    # -------------------------
                    # 📩 от клиента
                    # -------------------------
                    if isinstance(result, str):
                        data = json.loads(result)

                        # heartbeat
                        if data["type"] == "ping":
                            await set_user_online(str(user_id))
                            continue

                        chat_id = UUID(data["chat_id"])

                        # подписка (один раз)
                        if not pubsub.subscribed:
                            await pubsub.subscribe(f"chat:{chat_id}", "presence")

                        # -------------------------
                        # MESSAGE
                        # -------------------------
                        if data["type"] == "message":
                            text = data["text"]

                            # 🚀 O(1) seq
                            next_seq = await get_next_seq(chat_id)

                            msg = Message(
                                chat_id=chat_id,
                                user_id=user_id,
                                seq=next_seq,
                                content=text,
                            )

                            db.add(msg)
                            await db.commit()
                            await db.refresh(msg)

                            message_data = {
                                "type": "message",
                                "id": str(msg.id),
                                "chat_id": str(chat_id),
                                "user_id": str(user_id),
                                "seq": msg.seq,
                                "text": text,
                                "created_at": msg.created_at.isoformat(),
                            }

                            await redis_client.publish(
                                f"chat:{chat_id}",
                                json.dumps(message_data)
                            )

                        # -------------------------
                        # ✍️ TYPING
                        # -------------------------
                        elif data["type"] == "typing":
                            key = f"{user_id}:{chat_id}"
                            now = time.time()

                            if key not in typing_throttle or now - typing_throttle[key] > 1:
                                typing_throttle[key] = now

                                typing_data = {
                                    "type": "typing",
                                    "chat_id": str(chat_id),
                                    "user_id": str(user_id),
                                    "is_typing": data.get("is_typing", True),
                                }

                                await redis_client.publish(
                                    f"chat:{chat_id}",
                                    json.dumps(typing_data)
                                )

                    # -------------------------
                    # 📡 из Redis
                    # -------------------------
                    elif isinstance(result, dict) and result:
                        try:
                            data = json.loads(result["data"])
                            await safe_send(websocket, data)
                        except json.JSONDecodeError:
                            continue

                for task in pending:
                    task.cancel()

        except WebSocketDisconnect:
            await set_user_offline(str(user_id))
        finally:
            if chat_id:
                await pubsub.unsubscribe(f"chat:{chat_id}", "presence")
            await pubsub.close()