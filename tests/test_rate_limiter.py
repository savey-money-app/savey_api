import asyncio
from types import SimpleNamespace

import pytest
from starlette.responses import Response

from core.rate_limiter import ConcurrencyLimiter, RateLimiter, RateLimitMiddleware


def request_for(path: str, user_id=None, client_host="127.0.0.1"):
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        state=SimpleNamespace(user_id=user_id),
        client=SimpleNamespace(host=client_host) if client_host else None,
    )


@pytest.mark.anyio
async def test_rate_limiter_consumes_tokens_and_resets(monkeypatch):
    limiter = RateLimiter(rate=1, window=60)

    assert await limiter.is_allowed("user")
    assert not await limiter.is_allowed("user")

    limiter.buckets["user"] = (0, 0)
    monkeypatch.setattr("core.rate_limiter.time.time", lambda: 61)
    assert await limiter.is_allowed("user")


@pytest.mark.anyio
async def test_concurrency_limiter_reuses_user_semaphore():
    limiter = ConcurrencyLimiter(max_per_user=1, max_global=2)

    assert await limiter.get_user_semaphore("user") is await limiter.get_user_semaphore("user")


@pytest.mark.anyio
async def test_middleware_skips_non_api_paths_and_uses_request_identity():
    middleware = RateLimitMiddleware(lambda _scope, _receive, _send: None)

    async def call_next(_request):
        return Response("ok")

    response = await middleware.dispatch(request_for("/health"), call_next)

    assert response.body == b"ok"
    assert not middleware.should_rate_limit("/docs")
    assert middleware.should_rate_limit("/api/v1/users")
    assert middleware.get_user_id_from_request(request_for("/api/v1/users", "user-1")) == "user-1"
    assert middleware.get_user_id_from_request(request_for("/api/v1/users", client_host=None)) == "ip:unknown"


@pytest.mark.anyio
async def test_middleware_rejects_rate_limited_requests(monkeypatch):
    middleware = RateLimitMiddleware(lambda _scope, _receive, _send: None)

    async def reject(_user_id):
        return False

    monkeypatch.setattr(middleware.rate_limiter, "is_allowed", reject)
    response = await middleware.dispatch(request_for("/api/v1/users"), lambda _request: None)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == str(middleware.rate_limiter.window)


@pytest.mark.anyio
async def test_middleware_rejects_global_capacity():
    middleware = RateLimitMiddleware(
        lambda _scope, _receive, _send: None,
        max_concurrent_global=1,
    )
    await middleware.concurrency_limiter.global_semaphore.acquire()

    response = await middleware.dispatch(request_for("/api/v1/users"), lambda _request: None)

    assert response.status_code == 503
    middleware.concurrency_limiter.global_semaphore.release()


@pytest.mark.anyio
async def test_middleware_rejects_user_capacity(monkeypatch):
    middleware = RateLimitMiddleware(lambda _scope, _receive, _send: None)

    async def timeout(_awaitable, timeout):
        _awaitable.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr("core.rate_limiter.asyncio.wait_for", timeout)
    response = await middleware.dispatch(request_for("/api/v1/users"), lambda _request: None)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "2"


@pytest.mark.anyio
async def test_middleware_releases_capacity_after_response():
    middleware = RateLimitMiddleware(
        lambda _scope, _receive, _send: None,
        max_concurrent_per_user=1,
        max_concurrent_global=1,
    )

    async def call_next(_request):
        return Response("ok")

    response = await middleware.dispatch(request_for("/api/v1/users"), call_next)
    user_semaphore = await middleware.concurrency_limiter.get_user_semaphore("ip:127.0.0.1")

    assert response.body == b"ok"
    assert not middleware.concurrency_limiter.global_semaphore.locked()
    assert not user_semaphore.locked()
