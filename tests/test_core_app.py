import base64
import sys
from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import Response

import api
from core import database, redis


def request(path, headers=None):
    raw_headers = [
        (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": raw_headers,
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
            "server": ("test", 80),
            "query_string": b"",
        }
    )


@pytest.mark.anyio
async def test_docs_access_middleware():
    middleware = api.DocsAccessMiddleware(lambda *_args: None)

    async def call_next(_request):
        return Response("docs")

    unauthorized = await middleware.dispatch(request("/docs"), call_next)
    basic = base64.b64encode(b"admin:password").decode()
    authorized = await middleware.dispatch(
        request("/docs", {"authorization": f"Basic {basic}"}), call_next
    )
    passthrough = await middleware.dispatch(request("/health"), call_next)

    assert unauthorized.status_code == 401
    assert authorized.body == b"docs"
    assert passthrough.body == b"docs"


@pytest.mark.anyio
async def test_user_id_middleware(monkeypatch):
    middleware = api.UserIDExtractorMiddleware(lambda *_args: None)
    monkeypatch.setitem(sys.modules, "jwt", SimpleNamespace(decode=lambda *_args, **_kwargs: {"sub": "user"}))

    async def call_next(value):
        assert value.state.user_id == "user"
        return Response("ok")

    response = await middleware.dispatch(
        request("/api/v1/users", {"authorization": "Bearer token"}), call_next
    )

    assert response.body == b"ok"

    def explode(*_args, **_kwargs):
        raise ValueError("bad token")

    monkeypatch.setitem(sys.modules, "jwt", SimpleNamespace(decode=explode))
    async def invalid_next(_request):
        return Response("ok")

    assert (
        await middleware.dispatch(
            request("/api/v1/users", {"authorization": "Bearer bad"}), invalid_next
        )
    ).body == b"ok"


@pytest.mark.anyio
async def test_app_lifecycle(monkeypatch):
    events = []

    class Redis:
        async def ping(self):
            events.append("ping")

    async def get_redis():
        return Redis()

    async def close_redis():
        events.append("close")

    monkeypatch.setattr(redis, "get_redis", get_redis)
    monkeypatch.setattr(redis, "close_redis", close_redis)

    await api.startup_event()
    await api.shutdown_event()

    assert events == ["ping", "close"]


def test_database_dependency_commits_and_rolls_back(monkeypatch):
    class Session:
        def __init__(self):
            self.events = []

        def execute(self, *_args):
            self.events.append("execute")

        def commit(self):
            self.events.append("commit")

        def rollback(self):
            self.events.append("rollback")

        def close(self):
            self.events.append("close")

    success = Session()
    monkeypatch.setattr(database, "SessionLocal", lambda: success)
    generator = database.get_db()
    assert next(generator) is success
    with pytest.raises(StopIteration):
        next(generator)
    assert success.events == ["execute", "commit", "close"]

    failure = Session()
    monkeypatch.setattr(database, "SessionLocal", lambda: failure)
    generator = database.get_db()
    next(generator)
    with pytest.raises(RuntimeError):
        generator.throw(RuntimeError("boom"))
    assert failure.events == ["execute", "rollback", "close"]


@pytest.mark.anyio
async def test_redis_helpers(monkeypatch):
    closed = []

    class Redis:
        async def aclose(self):
            closed.append(True)

    monkeypatch.setattr(redis.aioredis, "from_url", lambda *_args, **_kwargs: Redis())
    monkeypatch.setattr(redis, "_redis", None)
    assert await redis.get_redis() is await redis.get_redis()
    await redis.close_redis()
    assert closed == [True]
