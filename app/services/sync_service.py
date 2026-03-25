from sqlalchemy import select, update
from app.models import Message, ChatState


async def sync_chat(db, user_id, chat_id, last_seen):
    result = await db.execute(
        select(Message)
        .where(
            Message.chat_id == chat_id,
            Message.seq > last_seen
        )
        .order_by(Message.seq)
        .limit(1000)
    )

    messages = result.scalars().all()

    if messages:
        max_seq = messages[-1].seq

        await db.execute(
            update(ChatState)
            .where(
                ChatState.user_id == user_id,
                ChatState.chat_id == chat_id
            )
            .values(last_delivered_seq=max_seq)
        )

    return messages