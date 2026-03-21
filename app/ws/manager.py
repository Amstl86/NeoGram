import json
import uuid
from collections import defaultdict
from typing import Dict, Set

from fastapi import WebSocket
from sqlalchemy import update, func
from starlette.websockets import WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import ChatMember, Message


connections_by_user: Dict[uuid.UUID, Set[WebSocket]] = defaultdict(set)

async def connect(ws: WebSocket, user_id: uuid.UUID):
    await ws.accept()
    connections_by_user[user_id].add(ws)

async def disconnect(ws: WebSocket, user_id: uuid.UUID):
    connections_by_user[user_id].discard(ws)

    if not connections_by_user[user_id]:
        del connections_by_user[user_id]

async def safe_send(ws: WebSocket, data: dict):
    try:
        await ws.send_json(data)
    except (WebSocketDisconnect, RuntimeError):
        return False
    return True

async def broadcast_to_user(user_id: uuid.UUID, payload: dict):
    """Отправка payload на все устройства пользователя"""
    conns = connections_by_user.get(user_id, [])
    for ws_conn in conns:
        await safe_send(ws_conn, payload)


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
    # валидация
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

    # membership через Redis (без БД)
    is_member = await redis.sismember(
        f"chat:{chat_id}:members",
        str(user_id)
    )

    if not is_member:
        return

    # seq генерация
    seq = await redis.incr(f"chat:{chat_id}:seq")

    # сохраняем
    msg = Message(
        chat_id=chat_id,
        user_id=user_id,
        content=text,
        seq=seq,
    )

    db.add(msg)
    await db.flush()   # лучше чем сразу commit
    await db.commit()


    payload = {
        "type": "new_message",
        "chat_id": str(chat_id),
        "seq": seq,
        "user_id": str(user_id),
        "text": text,
    }


    await redis.publish(
        f"chat:{chat_id}",
        json.dumps(payload)
    )

async def handle_state_update(
    data: dict,
    user_id: uuid.UUID,
    db: AsyncSession,
    redis
):
    chat_id_raw = data.get("chat_id")
    delivered_seq = data.get("delivered_seq")
    read_seq = data.get("read_seq")

    if not chat_id_raw:
        return

    try:
        chat_id = uuid.UUID(chat_id_raw)
    except ValueError:
        return

    values = {}
    returning_fields = []

    # 📦 delivered update
    if delivered_seq is not None:
        values["last_delivered_seq"] = func.greatest(
            ChatMember.last_delivered_seq,
            delivered_seq
        )
        returning_fields.append(ChatMember.last_delivered_seq)

    # 👁 read update
    if read_seq is not None:
        values["last_read_seq"] = func.greatest(
            ChatMember.last_read_seq,
            func.least(
                read_seq,
                ChatMember.last_delivered_seq
            )
        )
        returning_fields.append(ChatMember.last_read_seq)

    if not values:
        return

    stmt = (
        update(ChatMember)
        .where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == user_id
        )
        .values(**values)
        .returning(*returning_fields)
    )

    result = await db.execute(stmt)
    row = result.first()

    if not row:
        return

    await db.commit()

    # 📡 формируем payload
    payload = {
        "type": "state_update",
        "chat_id": str(chat_id),
        "user_id": str(user_id),
    }

    idx = 0

    if delivered_seq is not None:
        payload["delivered_seq"] = row[idx]
        idx += 1

    if read_seq is not None:
        payload["read_seq"] = row[idx]

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
                await disconnect(ws, uid)


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

            if not msg_type:
                continue

            # 📩 отправка сообщений
            if msg_type == "send_message":
                await handle_send_message(data, user_id, db, redis)

            # 🔄 новый unified handler
            elif msg_type == "state_update":
                await handle_state_update(data, user_id, db, redis)

            else:
                # защита от мусора
                await broadcast_to_user(user_id, {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}"
                })

    except WebSocketDisconnect:
        pass

    finally:
        await disconnect(ws, user_id)


