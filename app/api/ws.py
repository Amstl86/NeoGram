import json
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.ws.manager import manager
from app.core.redis import redis_client
from app.database import AsyncSessionLocal
from app.models import Message

router = APIRouter()


@router.websocket("/ws/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: UUID):

    # временно пользователь
    # позже будет из JWT
    user_id = UUID("11111111-1111-1111-1111-111111111111")

    await manager.connect(chat_id, websocket)

    async with AsyncSessionLocal() as db:  # type: AsyncSession

        try:
            while True:

                data = await websocket.receive_json()

                text = data["content"]

                # сохраняем сообщение
                msg = Message(
                    chat_id=chat_id,
                    user_id=user_id,
                    content=text
                )

                db.add(msg)
                await db.commit()
                await db.refresh(msg)

                message = {
                    "id": str(msg.id),
                    "chat_id": str(chat_id),
                    "user_id": str(user_id),
                    "content": text,
                    "created_at": msg.created_at.isoformat()
                }

                await redis_client.publish(
                    f"chat:{chat_id}",
                    json.dumps(message)
                )

        except WebSocketDisconnect:
            manager.disconnect(chat_id, websocket)