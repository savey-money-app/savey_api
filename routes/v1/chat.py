"""Chat endpoint: publishes to Redis queue, returns full or streamed SSE response"""
import asyncio
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.config import settings
from core.redis import get_redis
from routes.v1.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["Chat"])

RESPONSE_TIMEOUT = 60  # seconds to wait for LLM response


class ChatRequest(BaseModel):
    message: str
    context: dict | None = None
    hitl_flow_id: str | None = None
    hitl_action: str | None = None


def _build_job(user_id: str, request: ChatRequest) -> tuple[str, dict]:
    """Build the Redis job payload, return (message_id, job_dict)."""
    message_id = str(uuid.uuid4())
    job = {
        "user_id": user_id,
        "message_id": message_id,
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat(),
        "context": request.context,
        "hitl_flow_id": request.hitl_flow_id,
        "hitl_action": request.hitl_action,
    }
    return message_id, job


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user_id: str = Depends(get_current_user),
):
    """
    Send a message to the LLM worker and stream the response back as SSE.

    Each SSE frame carries a JSON payload. A final `data: [DONE]` frame closes the stream.
    """
    message_id, job = _build_job(current_user_id, request)
    redis = await get_redis()
    await redis.lpush(settings.REDIS_CHAT_QUEUE, json.dumps(job))

    channel = f"{settings.REDIS_CHAT_CHANNEL_PREFIX}:{message_id}"

    async def event_stream():
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            deadline = datetime.utcnow().timestamp() + RESPONSE_TIMEOUT
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


@router.post("/message")
async def chat_message(
    request: ChatRequest,
    current_user_id: str = Depends(get_current_user),
):
    """
    Send a message to the LLM worker and wait for the full response.

    Blocks until the worker publishes the response (or timeout).
    """
    message_id, job = _build_job(current_user_id, request)
    redis = await get_redis()

    channel = f"{settings.REDIS_CHAT_CHANNEL_PREFIX}:{message_id}"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    # Push AFTER subscribing to avoid missing the response
    await redis.lpush(settings.REDIS_CHAT_QUEUE, json.dumps(job))

    try:
        payload = None
        deadline = asyncio.get_event_loop().time() + RESPONSE_TIMEOUT
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            data = raw["data"]
            if data == "[DONE]":
                break
            payload = json.loads(data)
            if asyncio.get_event_loop().time() > deadline:
                raise HTTPException(status_code=504, detail="LLM response timeout")
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()

    if payload is None:
        raise HTTPException(status_code=504, detail="LLM response timeout")

    return {"message_id": message_id, **payload}
