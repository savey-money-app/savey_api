"""Chat endpoint: publishes to Redis queue, streams SSE response back"""
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.config import settings
from core.redis import get_redis
from routes.v1.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["Chat"])

STREAM_TIMEOUT = 60  # seconds to wait for LLM response


class ChatRequest(BaseModel):
    message: str
    context: dict | None = None
    hitl_flow_id: str | None = None
    hitl_action: str | None = None


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user_id: str = Depends(get_current_user),
):
    """
    Send a message to the LLM worker via Redis queue and stream the response back as SSE.

    Flow:
    1. Push job to chat_queue (list)
    2. Subscribe to chat:{message_id} pubsub channel
    3. Stream chunks as SSE until [DONE] sentinel received
    """
    message_id = str(uuid.uuid4())
    redis = await get_redis()

    # Build the job payload matching savey_llm MessageInput schema
    job = {
        "user_id": current_user_id,
        "message_id": message_id,
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat(),
        "context": request.context,
        "hitl_flow_id": request.hitl_flow_id,
        "hitl_action": request.hitl_action,
    }

    # Push to queue (worker does brpop)
    await redis.lpush(settings.REDIS_CHAT_QUEUE, json.dumps(job))

    channel = f"{settings.REDIS_CHAT_CHANNEL_PREFIX}:{message_id}"

    async def event_stream():
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            # Wait for messages with timeout
            deadline = datetime.utcnow().timestamp() + STREAM_TIMEOUT
            async for raw in pubsub.listen():
                if raw["type"] != "message":
                    continue
                data = raw["data"]
                if data == "[DONE]":
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {data}\n\n"
                if datetime.utcnow().timestamp() > deadline:
                    yield "data: [ERROR] timeout\n\n"
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Message-ID": message_id,
        },
    )
