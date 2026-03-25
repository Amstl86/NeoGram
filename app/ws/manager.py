import uuid

from collections import defaultdict
from typing import Dict, Set

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


connections_by_user: Dict[uuid.UUID, Set[WebSocket]] = defaultdict(set)

async def connect(ws: WebSocket, user_id: uuid.UUID):
    await ws.accept()
    connections_by_user[user_id].add(ws)

async def disconnect(ws: WebSocket, user_id: uuid.UUID):
    if user_id not in connections_by_user:
        return

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
