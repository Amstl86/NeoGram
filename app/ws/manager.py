import json
import uuid
from collections import defaultdict
from typing import Dict, Set

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import ChatMember, Message


connections_by_user: Dict[uuid.UUID, Set[WebSocket]] = defaultdict(set)

async def connect(ws: WebSocket, user_id: uuid.UUID):
    await ws.accept()
    connections_by_user[user_id].add(ws)

def disconnect(ws: WebSocket, user_id: uuid.UUID):
    connections_by_user[user_id].discard(ws)

    if not connections_by_user[user_id]:
        del connections_by_user[user_id]

async def safe_send(ws: WebSocket, data: dict):
    try:
        await ws.send_json(data)
    except (WebSocketDisconnect, RuntimeError):
        return False
    return True

async def get_chat_members(chat_id, db, redis):
    key = f"chat:{chat_id}:members"

    members = await redis.smembers(key)

    if members:
        return [uuid.UUID(uid) for uid in members]

    # fallback
    result = await db.execute(
        select(ChatMember.user_id).where(
            ChatMember.chat_id == chat_id
        )
    )

    user_ids = [row[0] for row in result.all()]

    if user_ids:
        await redis.sadd(key, *[str(uid) for uid in user_ids])

    return user_ids

async def handle_send_message(
    data: dict,
    user_id: uuid.UUID,
    db: AsyncSession,
    redis
):
    # 🔒 1. валидация
    chat_id_raw = data.get("chat_id")
    text = data.get("text")

    if not chat_id_raw or not text:
        return

    text = text.strip()
    if not text:
        return

    try:
        chat_id = uuid.UUID(chat_id_raw)
    except ValueError:
        return

    # ⚡ 2. membership через Redis (без БД)
    is_member = await redis.sismember(
        f"chat:{chat_id}:members",
        str(user_id)
    )

    if not is_member:
        return

    # ⚡ 3. seq генерация
    seq = await redis.incr(f"chat:{chat_id}:seq")

    # 💾 4. сохраняем
    msg = Message(
        chat_id=chat_id,
        user_id=user_id,
        content=text,
        seq=seq,
    )

    db.add(msg)
    await db.flush()   # лучше чем сразу commit
    await db.commit()

    # 📡 5. payload
    payload = {
        "type": "new_message",
        "chat_id": str(chat_id),
        "seq": seq,
        "user_id": str(user_id),
        "text": text,
    }

    # 🚀 6. publish
    await redis.publish(
        f"chat:{chat_id}",
        json.dumps(payload)
    )

async def handle_ack(
    data: dict,
    user_id: uuid.UUID,
    db: AsyncSession,
    redis
):
    chat_id_raw = data.get("chat_id")
    seq = data.get("seq")

    if not chat_id_raw or seq is None:
        return

    try:
        chat_id = uuid.UUID(chat_id_raw)
    except ValueError:
        return

    # 🔒 membership
    result = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == user_id
        )
    )

    member = result.scalar_one_or_none()
    if not member:
        return

    # 📈 обновляем delivered
    if seq > member.last_delivered_seq:
        member.last_delivered_seq = seq
        await db.commit()

        # 📡 уведомляем остальных
        payload = {
            "type": "message_delivered",
            "chat_id": str(chat_id),
            "user_id": str(user_id),
            "seq": seq,
        }

        await redis.publish(
            f"chat:{chat_id}",
            json.dumps(payload)
        )

async def redis_listener(db: AsyncSession, redis):
    pubsub = redis.pubsub()
    await pubsub.psubscribe("chat:*")

    async for msg in pubsub.listen():
        if msg["type"] != "pmessage":
            continue

        data = json.loads(msg["data"])
        chat_id = data["chat_id"]

        user_ids = await get_chat_members(chat_id, db, redis)

        for uid in user_ids:
            connections = connections_by_user.get(uid)

            if not connections:
                continue

            dead = []

            for ws in connections:
                ok = await safe_send(ws, data)
                if not ok:
                    dead.append(ws)

            for ws in dead:
                disconnect(ws, uid)

async def websocket_handler(
    ws: WebSocket,
    user_id: uuid.UUID,
    db: AsyncSession,
    redis
):
    await connect(ws, user_id)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "send_message":
                await handle_send_message(data, user_id, db, redis)

            elif msg_type == "ack":
                await handle_ack(data, user_id, db, redis)

    except WebSocketDisconnect:
        pass

    finally:
        disconnect(ws, user_id)


































# from fastapi import WebSocket
# from typing import Dict, Set
# from uuid import UUID
# from starlette.websockets import WebSocketDisconnect
# import asyncio
#
#
# class ConnectionManager:
#
#     def __init__(self):
#         self.active_connections: Dict[UUID, Set[WebSocket]] = {}
#         self.queue = asyncio.Queue()
#
#     async def connect(self, chat_id: UUID, websocket: WebSocket):
#         await websocket.accept()
#
#         if chat_id not in self.active_connections:
#             self.active_connections[chat_id] = set()
#
#         self.active_connections[chat_id].add(websocket)
#
#     def disconnect(self, chat_id: UUID, websocket: WebSocket):
#
#         if chat_id not in self.active_connections:
#             return
#
#         self.active_connections[chat_id].discard(websocket)
#
#         if not self.active_connections[chat_id]:
#             del self.active_connections[chat_id]
#
#     async def broadcast(self, chat_id: UUID, message: dict):
#         await self.queue.put((chat_id, message))
#
#     async def worker(self):
#
#         while True:
#
#             chat_id, message = await self.queue.get()
#
#             if chat_id not in self.active_connections:
#                 continue
#
#             dead = []
#
#             for ws in self.active_connections[chat_id]:
#
#                 try:
#                     await ws.send_json(message)
#
#                 except WebSocketDisconnect:
#                     dead.append(ws)
#
#                 except RuntimeError:
#                     dead.append(ws)
#
#             for ws in dead:
#                 self.disconnect(chat_id, ws)
#
#
# manager = ConnectionManager()