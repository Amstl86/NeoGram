from fastapi import APIRouter

from app.core.redis import redis_client

router = APIRouter()


@router.get("/users/{user_id}/status")
async def get_user_status(user_id: str):
    online = await redis_client.get(f"user:{user_id}:online")

    if online:
        return {"status": "online"}

    last_seen = await redis_client.get(f"user:{user_id}:last_seen")

    return {
        "status": "offline",
        "last_seen": int(last_seen) if last_seen else None
    }