import asyncio

from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.routers import auth, chats
from app.api import ws
from app.ws.redis_listener import redis_listener
from app.ws.manager import manager
from app.api.chats import delivered

app = FastAPI()

app.include_router(auth.router)
app.include_router(chats.router)

app.include_router(ws.router)
app.include_router(chats.router)
app.include_router(delivered.router)
@app.get("/")
async def root():
    return {"status": "Messenger backend running"}

@asynccontextmanager
async def lifespan(_app: FastAPI):

    # запуск фонового Redis listener
    task = asyncio.create_task(redis_listener())

    yield

    # корректная остановка при shutdown
    task.cancel()
@asynccontextmanager
async def lifespan(_app: FastAPI):

    worker = asyncio.create_task(manager.worker())

    yield

    worker.cancel()

app = FastAPI(lifespan=lifespan)