import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.redis import get_redis

from app.dependencies import get_db, get_current_user
from app.models import Chat, ChatMember, User
from app.schemas import ChatCreate
from app.api.chats import messages

router = APIRouter(
    prefix="/chats",
    tags=["chats"]
)

router.include_router(messages.router, prefix="", tags=["messages"])



@router.post("/private")
async def create_private_chat(
    data: ChatCreate,
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    chat = Chat(type="private")

    db.add(chat)
    await db.flush()

    members = [
        ChatMember(user_id=current_user.id, chat_id=chat.id, role="member"),
        ChatMember(user_id=data.user_id, chat_id=chat.id, role="member"),
    ]

    db.add_all(members)
    await db.commit()

    # 🔥 кешируем участников
    await redis.sadd(
        f"chat:{chat.id}:members",
        str(current_user.id),
        str(data.user_id)
    )

    return {"chat_id": chat.id}

@router.post("/group")
async def create_group_chat(
    title: str,
    user_ids: List[uuid.UUID],
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    chat = Chat(
        type="group",
        title=title,
        owner_id=current_user.id,
    )

    db.add(chat)
    await db.flush()

    members = [
        ChatMember(
            user_id=current_user.id,
            chat_id=chat.id,
            role="owner"
        ),
        *[
            ChatMember(
                user_id=uid,
                chat_id=chat.id,
                role="member"
            )
            for uid in dict.fromkeys(user_ids)
            if uid != current_user.id
        ]
    ]

    db.add_all(members)
    await db.commit()

    # 🔥 кеш участников
    await redis.sadd(
        f"chat:{chat.id}:members",
        *[str(m.user_id) for m in members]
    )

    return {
        "chat_id": chat.id,
        "type": chat.type,
        "title": chat.title,
    }

@router.get("/")
async def get_chats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Chat, ChatMember)
        .join(ChatMember, Chat.id == ChatMember.chat_id)
        .where(ChatMember.user_id == current_user.id)
    )

    rows = result.all()

    chats = []

    for chat, member in rows:
        chats.append({
            "chat_id": chat.id,
            "type": chat.type,
            "title": chat.title,
            "last_read_seq": member.last_read_seq,
        })

    return chats






























# from fastapi import APIRouter, Depends
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
# from uuid import UUID
#
# from app.dependencies import get_db, get_current_user
# from app.models import Chat, ChatMember, User
# from app.schemas import ChatCreate
# from app.api.chats import messages
#
# router = APIRouter(
#     prefix="/chats",
#     tags=["chats"]
# )
# router.include_router(messages.router, prefix="/chats", tags=["chats"])
#
# @router.post("/private")
# async def create_private_chat(
#         data: ChatCreate,
#         db: AsyncSession = Depends(get_db),
#         current_user: User = Depends(get_current_user),
# ):
#
#     chat = Chat(type=False)
#
#     db.add(chat)
#     await db.flush()
#
#     member1 = ChatMember(
#         user_id=current_user.id,
#         chat_id=chat.id
#     )
#
#     member2 = ChatMember(
#         user_id=data.user_id,
#         chat_id=chat.id
#     )
#
#     db.add_all([member1, member2])
#
#     await db.commit()
#
#     return {"chat_id": chat.id}
#
# @router.get("/")
# async def get_chats(
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ):
#
#     result = await db.execute(
#         select(Chat)
#         .join(ChatMember)
#         .where(ChatMember.user_id == current_user.id)
#     )
#
#     chats = result.scalars().all()
#
#     return chats
#
# @router.post("/")
# async def create_chat(
#     user_ids: list[UUID],
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ):
#
#     chat = Chat()
#
#     db.add(chat)
#     await db.flush()
#
#     members = [
#         ChatMember(chat_id=chat.id, user_id=current_user.id)
#     ]
#
#     for uid in user_ids:
#         members.append(
#             ChatMember(chat_id=chat.id, user_id=uid)
#         )
#
#     db.add_all(members)
#
#     await db.commit()
#
#     return {"chat_id": chat.id
#
#
# @router.post("/chats/group")
# async def create_group_chat(
#     title: str,
#     user_ids: list[UUID],
#     db: AsyncSession = Depends(get_db),
#     user: User = Depends(get_current_user),
# ):
#     chat = Chat(
#         type="group",
#         title=title,
#         owner_id=user.id,
#     )
#
#     db.add(chat)
#     await db.flush()  # получаем chat.id
#
#     members = []
#
#     # creator = owner
#     members.append(ChatMember(
#         user_id=user.id,
#         chat_id=chat.id,
#         role="owner"
#     ))
#
#     # остальные участники
#     for uid in set(user_ids):  # защита от дублей
#         if uid == user.id:
#             continue
#
#         members.append(ChatMember(
#             user_id=uid,
#             chat_id=chat.id,
#             role="member"
#         ))
#
#     db.add_all(members)
#     await db.commit()
#
#     return {
#         "chat_id": chat.id,
#         "type": chat.type,
#         "title": chat.title,
#     }