import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.routers import auth, chats
from app.api import ws
from app.api.chats import delivered

from app.ws.redis_listener import redis_listener
from app.workers.retry_worker import retry_pending_worker
from app.core.redis import redis_client
from app.database import AsyncSessionLocal


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # создаём DB session для listener
    db = AsyncSessionLocal()

    listener_task = asyncio.create_task(
        redis_listener(db, redis_client)
    )

    retry_task = asyncio.create_task(
        retry_pending_worker(redis_client)
    )

    yield

    # shutdown
    listener_task.cancel()
    retry_task.cancel()

    await db.close()


app = FastAPI(lifespan=lifespan)

# ✅ роутеры подключаем ПОСЛЕ создания app
app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(ws.router)
app.include_router(delivered.router)


@app.get("/")
async def root():
    return {"status": "Messenger backend running"}