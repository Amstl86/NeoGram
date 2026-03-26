import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.core.redis import get_redis
from app.services.sync_service import get_messages_after_f

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/messages/{chat_id}")
async def get_messages_after(
    chat_id: str,
    from_seq: int = Query(..., ge=0),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db)
):
    """
    🔥 GAP RECOVERY endpoint

    Возвращает сообщения:
    seq > from_seq
    """

    messages = await get_messages_after_f(db, chat_id, from_seq, limit)

    return [
        {
            "type": "message",
            "chat_id": str(m.chat_id),
            "seq": m.seq,
            "sender_id": str(m.sender_id),
            "text": m.content,
        }
        for m in messages
    ]

# ⚡ быстрый GAP через Redis
@router.get("/messages_cached/{chat_id}")
async def get_cached(
    chat_id: str,
    from_seq: int,
    redis=Depends(get_redis)
):
    msgs = await redis.zrangebyscore(
        f"chat:{chat_id}:history",
        from_seq + 1,
        "+inf"
    )

    return [json.loads(m) for m in msgs]