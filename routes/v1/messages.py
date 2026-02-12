"""Message routes: chat endpoints and message history"""
import asyncio
import base64
import json
import mimetypes
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.redis import get_redis
from routes.v1.auth import get_current_user
from schemas.message import MessageResponse, MessageCreate
from services.message_service import create_message, get_user_messages
from services.user_service import get_user_by_id

router = APIRouter(prefix="/messages", tags=["Messages"])

RESPONSE_TIMEOUT = 60  # seconds to wait for LLM response


# ── Schemas ──────────────────────────────────────────────────────────

class UserMetadata(BaseModel):
    user_fullname: Optional[str] = None
    user_currency: str


class ChatRequest(BaseModel):
    message: str
    file_ids: Optional[List[str]] = None


# ── Helpers ──────────────────────────────────────────────────────────

def _resolve_attachments(file_ids: Optional[List[str]]) -> List[dict]:
    """
    Resolve file IDs to base64-encoded attachment dicts.

    Each file_id corresponds to a directory under UPLOADS_DIR/{file_id}/
    containing the uploaded file. The file is read, base64-encoded, and
    returned as a MessageAttachment-compatible dict.
    """
    if not file_ids:
        return []

    attachments = []
    for file_id in file_ids:
        upload_dir = Path(settings.UPLOADS_DIR) / file_id
        if not upload_dir.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

        # Find the file inside the uuid directory (there's exactly one)
        files = list(upload_dir.iterdir())
        if not files:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

        filepath = files[0]
        mime_type, _ = mimetypes.guess_type(str(filepath))
        mime_type = mime_type or "application/octet-stream"

        data = base64.b64encode(filepath.read_bytes()).decode("utf-8")
        attachments.append({
            "data": data,
            "mime_type": mime_type,
            "filename": filepath.name,
            "size": filepath.stat().st_size,
        })

    return attachments


def _build_job(user_id: str, request: ChatRequest, user_metadata: UserMetadata) -> tuple[str, dict]:
    """Build the Redis job payload, return (message_id, job_dict)."""
    message_id = str(uuid.uuid4())
    job = {
        "user_id": user_id,
        "message_id": message_id,
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat(),
        "user_metadata": user_metadata.model_dump(),
        "attachments": _resolve_attachments(request.file_ids),
    }
    return message_id, job


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/stream")
async def message_stream(
    request: ChatRequest,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a message to the LLM worker and stream the response back as SSE.

    Each SSE frame carries a JSON payload. A final `data: [DONE]` frame closes the stream.
    Both user and LLM messages are persisted after the stream completes.
    """
    user = get_user_by_id(db, current_user_id)
    user_metadata = UserMetadata(user_fullname=user.full_name, user_currency=user.currency)
    had_attachment = bool(request.file_ids)
    message_id, job = _build_job(current_user_id, request, user_metadata)
    redis = await get_redis()
    await redis.lpush(settings.REDIS_CHAT_QUEUE, json.dumps(job))

    channel = f"{settings.REDIS_CHAT_CHANNEL_PREFIX}:{message_id}"

    async def event_stream():
        accumulated_content = []
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
                # Accumulate LLM response chunks
                try:
                    chunk = json.loads(data)
                    if isinstance(chunk, dict) and "content" in chunk:
                        accumulated_content.append(chunk["content"])
                except (json.JSONDecodeError, TypeError):
                    accumulated_content.append(data)
                yield f"data: {data}\n\n"
                if datetime.utcnow().timestamp() > deadline:
                    yield "data: [ERROR] timeout\n\n"
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

            # Persist both messages after stream completes
            llm_content = "".join(accumulated_content)
            if llm_content:
                create_message(db, MessageCreate(content=request.message, is_user=True, had_attachment=had_attachment, user_id=current_user_id))
                create_message(db, MessageCreate(content=llm_content, is_user=False, had_attachment=False, user_id=current_user_id))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Message-ID": message_id,
        },
    )


@router.post("/send")
async def message_send(
    request: ChatRequest,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
)->:
    """
    Send a message to the LLM worker and wait for the full response.

    Blocks until the worker publishes the response (or timeout).
    Both user and LLM messages are persisted to the database.
    """
    user = get_user_by_id(db, current_user_id)
    user_metadata = UserMetadata(user_fullname=user.full_name, user_currency=user.currency)
    had_attachment = bool(request.file_ids)
    message_id, job = _build_job(current_user_id, request, user_metadata)
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

    # Persist both messages (skip if LLM returned empty content)
    llm_content = payload.get("content", "") if isinstance(payload, dict) else str(payload)
    if llm_content:
        create_message(db, MessageCreate(content=request.message, is_user=True, had_attachment=had_attachment, user_id=current_user_id))
        create_message(db, MessageCreate(content=llm_content, is_user=False, had_attachment=False, user_id=current_user_id))

    return MessageResponse(
        id=message_id,
        user_id=current_user_id,
        is_user=False,
        had_attachment=False,
        **payload,
    )


@router.get("", response_model=List[MessageResponse])
def list_messages(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get chat history for the current user (paginated)"""
    messages = get_user_messages(db, current_user_id, skip, limit)
    return messages
