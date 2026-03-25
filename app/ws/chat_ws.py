import uuid
import json

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.core.redis import redis_client
from app.core.presence import set_user_online, set_user_offline

from app.ws.manager import connect, disconnect, broadcast_to_user
from app.ws.handler import handle_send_message
from app.ws.handler import handle_state_update


async def chat_ws(websocket: WebSocket, user_id: uuid.UUID):
    await connect(websocket, user_id)

    # 🟢 online
    await set_user_online(str(user_id))

    async with AsyncSessionLocal() as db:  # type: AsyncSession
        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if not msg_type:
                    continue

                # ❤️ heartbeat
                if msg_type == "ping":
                    await set_user_online(str(user_id))
                    continue

                # 📩 сообщение
                elif msg_type == "send_message":
                    await handle_send_message(
                        data=data,
                        user_id=user_id,
                        db=db,
                        redis=redis_client
                    )

                # 🔄 delivered / read
                elif msg_type == "state_update":
                    await handle_state_update(
                        data=data,
                        user_id=user_id,
                        db=db,
                        redis=redis_client
                    )

                # ✍️ typing (optional)
                elif msg_type == "typing":
                    await redis_client.publish(
                        f"chat:{data['chat_id']}",
                        json.dumps({
                            "type": "typing",
                            "chat_id": data["chat_id"],
                            "user_id": str(user_id),
                            "is_typing": data.get("is_typing", True),
                        })
                    )

                # ❌ unknown
                else:
                    await broadcast_to_user(user_id, {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}"
                    })

        except WebSocketDisconnect:
            pass

        finally:
            # 🔴 offline
            await set_user_offline(str(user_id))
            await disconnect(websocket, user_id)