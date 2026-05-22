from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from core import settings
from core.rate_limiter import RateLimitMiddleware
from routes import router

logging.basicConfig(
    level=logging.INFO,  # or DEBUG for more verbosity
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

security = HTTPBasic(auto_error=False)

class DocsAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/docs", "/redoc"]:
            credentials: HTTPBasicCredentials = await security(request)
            if not (credentials and credentials.username == "admin" and credentials.password == "password"):
                # Return a 401 response with WWW-Authenticate header so the browser shows a login prompt.
                return Response(
                    content="Unauthorized",
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Docs"'}
                )
        response = await call_next(request)
        return response


class UserIDExtractorMiddleware(BaseHTTPMiddleware):
    """Extract user_id from JWT token and attach to request.state for rate limiting."""

    async def dispatch(self, request: Request, call_next):
        # Try to extract user_id from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = payload.get("sub")
                if user_id:
                    request.state.user_id = user_id
            except JWTError:
                # Invalid token, continue without user_id
                pass

        response = await call_next(request)
        return response

async def startup_event():
    """Initialize Redis connection on startup"""
    from core.redis import get_redis
    try:
        redis = await get_redis()
        await redis.ping()
        logging.info("Redis connection established successfully")
    except Exception as e:
        logging.error(f"Failed to connect to Redis: {e}")


async def shutdown_event():
    """Close Redis connection on shutdown"""
    from core.redis import close_redis
    try:
        await close_redis()
        logging.info("Redis connection closed")
    except Exception as e:
        logging.error(f"Error closing Redis connection: {e}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await startup_event()
    try:
        yield
    finally:
        await shutdown_event()


app = FastAPI(lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware)
app.add_middleware(DocsAccessMiddleware)

# Extract user_id from JWT token for rate limiting (must be before RateLimitMiddleware).
app.add_middleware(UserIDExtractorMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    rate_limit_requests=60,
    rate_limit_window=60,
    max_concurrent_per_user=5,
    max_concurrent_global=100,
    excluded_paths=["/docs", "/redoc", "/openapi.json", "/api/v1/llm/health"],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict via configuration.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
