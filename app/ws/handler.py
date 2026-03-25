import uuid
from fastapi import WebSocket, WebSocketDisconnect

from app.ws.manager import connect, disconnect
from app.services.message_service import handle_send_message
from app.services.state_service import handle_state_update


async def websocket_handler(ws: WebSocket, user_id: uuid.UUID, db, redis):
    await connect(ws, user_id)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "send_message":
                await handle_send_message(data, user_id, db, redis)

            elif msg_type == "state_update":
                await handle_state_update(data, user_id, db, redis)

            else:
                await ws.send_json({
                    "type": "error",
                    "message": f"Unknown type: {msg_type}"
                })

    except WebSocketDisconnect:
        pass

    finally:
        await disconnect(ws, user_id)