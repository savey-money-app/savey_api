from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # Production supplies its managed database URL through the environment.
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/savey"

    # JWT Authentication
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    # JWT_SECRET is shared with savey_auth microservice (Better Auth).
    # Set both to the same value in production. Defaults to SECRET_KEY for
    # backwards compatibility during migration.
    JWT_SECRET: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Redis (chat queue + pubsub)
    REDIS_URL: str = "redis://redis:6379"
    REDIS_CHAT_QUEUE: str = "chat_queue"
    REDIS_CHAT_CHANNEL_PREFIX: str = "chat"

    # Internal service auth (used by savey_llm to call API without user JWT)
    INTERNAL_API_TOKEN: str = "change-me-internal-secret"

    # File uploads
    UPLOADS_DIR: str = "/app/uploads"

    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Savey API"

    # Dokploy vars

    DOCKER_CONFIG: str = "docker"
    APP_NAME: str = "savey_api"
    COMPOSE_PROJECT_NAME: str = "api"
settings = Settings()

# SQLAlchemy 1.4+ dropped the bare "postgres://" dialect alias.
# Managed DBs (Render, Railway, Neon) still emit it — normalise here.
if settings.DATABASE_URL.startswith("postgres://"):
    settings.DATABASE_URL = settings.DATABASE_URL.replace("postgres://", "postgresql://", 1)
