import base64
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from routes.v1 import messages
from schemas.message import MessageCreate


def metadata():
    return messages.UserMetadata(
        user_fullname="Person",
        user_currency="KZT",
        user_preferred_language="en",
    )


def user():
    return SimpleNamespace(
        full_name="Person",
        currency="KZT",
        preferred_language="en",
    )


class PubSub:
    def __init__(self, payloads):
        self.payloads = payloads
        self.subscribed = []
        self.closed = False

    async def subscribe(self, channel):
        self.subscribed.append(channel)

    async def unsubscribe(self, channel):
        self.subscribed.remove(channel)

    async def aclose(self):
        self.closed = True

    async def listen(self):
        yield {"type": "subscribe", "data": None}
        for payload in self.payloads:
            yield {"type": "message", "data": payload}


class Redis:
    def __init__(self, payloads):
        self.pubsub_item = PubSub(payloads)
        self.pushed = []

    def pubsub(self):
        return self.pubsub_item

    async def lpush(self, key, value):
        self.pushed.append((key, json.loads(value)))


class SaveDB:
    def __init__(self):
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def execute(self, value):
        self.executed.append(value)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def redis_dependency(value):
    async def get_redis():
        return value

    return get_redis


def test_attachment_resolution_and_job(tmp_path, monkeypatch):
    monkeypatch.setattr(messages.settings, "UPLOADS_DIR", str(tmp_path))
    request = messages.ChatRequest(message="read this", file_ids=["file-1"])
    with pytest.raises(HTTPException, match="File not found"):
        messages._resolve_attachments(request.file_ids)

    upload = tmp_path / "file-1"
    upload.mkdir()
    with pytest.raises(HTTPException, match="File not found"):
        messages._resolve_attachments(request.file_ids)

    file_path = upload / "statement.pdf"
    file_path.write_bytes(b"pdf")
    attachments = messages._resolve_attachments(request.file_ids)
    message_id, job = messages._build_job(str(uuid4()), request, metadata())

    assert attachments[0]["data"] == base64.b64encode(b"pdf").decode()
    assert attachments[0]["mime_type"] == "application/pdf"
    assert job["message_id"] == message_id
    assert job["attachments"] == attachments
    assert messages._resolve_attachments(None) == []


@pytest.mark.anyio
async def test_message_send_and_history(monkeypatch):
    user_id = str(uuid4())
    payload = json.dumps({"content": "AI answer"})
    redis = Redis([payload, "[DONE]"])
    created = []
    monkeypatch.setattr(messages, "get_user_by_id", lambda *_args: user())
    monkeypatch.setattr(messages, "get_redis", redis_dependency(redis))
    monkeypatch.setattr(messages, "create_message", lambda _db, value: created.append(value))

    response = await messages.message_send(
        messages.ChatRequest(message="hello"), user_id, object()
    )

    assert response.content == "AI answer"
    assert [item.content for item in created] == ["hello", "AI answer"]
    monkeypatch.setattr(messages, "get_user_messages", lambda *_args: ["history"])
    assert messages.list_messages(0, 5, user_id, None) == ["history"]


@pytest.mark.anyio
async def test_message_send_times_out_without_payload(monkeypatch):
    redis = Redis(["[DONE]"])
    monkeypatch.setattr(messages, "get_user_by_id", lambda *_args: user())
    monkeypatch.setattr(messages, "get_redis", redis_dependency(redis))

    with pytest.raises(HTTPException) as exc_info:
        await messages.message_send(
            messages.ChatRequest(message="hello"), str(uuid4()), object()
        )

    assert exc_info.value.status_code == 504


@pytest.mark.anyio
async def test_message_stream_accumulates_chunks(monkeypatch):
    user_id = str(uuid4())
    redis = Redis(
        [
            json.dumps({"content": "Hello ", "balance": {"balance": 1}}),
            "raw",
            json.dumps({"content": "world", "hitl_data": {"flow": "confirm"}}),
            "[DONE]",
        ]
    )
    created: list[MessageCreate] = []
    save_db = SaveDB()
    monkeypatch.setattr(messages, "get_user_by_id", lambda *_args: user())
    monkeypatch.setattr(messages, "get_redis", redis_dependency(redis))
    monkeypatch.setattr(messages, "create_message", lambda _db, value: created.append(value))
    monkeypatch.setattr(messages, "SessionLocal", lambda: save_db)

    response = await messages.message_stream(
        messages.ChatRequest(message="stream"), user_id, object()
    )
    chunks = [chunk async for chunk in response.body_iterator]

    assert "Hello " in chunks[0]
    assert chunks[-1] == "data: [DONE]\n\n"
    assert [item.content for item in created] == ["stream", "Hello rawworld"]
    assert created[-1].hitl_data == {"flow": "confirm"}
    assert save_db.commits == 1


@pytest.mark.anyio
async def test_message_stream_skips_empty_ai_message(monkeypatch):
    redis = Redis(["[DONE]"])
    created = []
    monkeypatch.setattr(messages, "get_user_by_id", lambda *_args: user())
    monkeypatch.setattr(messages, "get_redis", redis_dependency(redis))
    monkeypatch.setattr(messages, "create_message", lambda _db, value: created.append(value))
    monkeypatch.setattr(messages, "SessionLocal", SaveDB)

    response = await messages.message_stream(
        messages.ChatRequest(message="stream"), str(uuid4()), object()
    )
    assert [chunk async for chunk in response.body_iterator][-1] == "data: [DONE]\n\n"
    assert [item.content for item in created] == ["stream"]
