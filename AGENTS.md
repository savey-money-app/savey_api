# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Savey API is a FastAPI-based personal finance REST API (Python 3.12, managed with `uv`). It stores data in PostgreSQL (Neon cloud) and uses Redis for chat queueing / pub-sub and rate limiting.

### Running the dev server

```bash
redis-server --daemonize yes
uv run uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### Key caveats

- **DATABASE_URL scheme**: SQLAlchemy requires `postgresql://`, not `postgres://`. The `.env.example` uses the latter — always use `postgresql://` in `.env`.
- **Neon pooler + search_path**: The Neon connection-pooler rejects `options=-c search_path=...` in the connection URL. Remove it; the code already sets `SET search_path TO savey` per-session in `core/database.py:get_db()`.
- **Redis must be running**: The app pings Redis on startup. It logs an error but still starts if Redis is down; however, chat and rate-limiting features will not work.
- **`.env` changes require server restart**: Uvicorn's `--reload` watches only `.py` files, so editing `.env` requires killing and restarting the server manually.
- **No test suite**: `pytest` is a dependency but no test files exist yet. `uv run pytest` exits cleanly with 0 tests collected.
- **No linter config**: No ruff/flake8/mypy configuration is present. Future agents adding lint checks should set one up.
- **UPLOADS_DIR**: Defaults to `/app/uploads` (Docker path). For local dev, set `UPLOADS_DIR` to a local directory (e.g. `./uploads`).
- **Docs auth**: `/docs` and `/redoc` are protected by HTTP Basic Auth (username: `admin`, password: `password`).
