from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database (Neon PostgreSQL) - Using 'savey' schema
    DATABASE_URL: str = "postgresql://neondb_owner:npg_zOQAHDxvM5h7@ep-green-pine-a2y91p4h-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require"

    # JWT Authentication
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Redis (chat queue + pubsub)
    REDIS_URL: str = "redis://redis:6379"
    REDIS_CHAT_QUEUE: str = "chat_queue"
    REDIS_CHAT_CHANNEL_PREFIX: str = "chat"

    # RabbitMQ (kept for reference, no longer used)
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_EXCHANGE: str = "savey"
    RABBITMQ_QUEUE: str = "llm_messages"
    RABBITMQ_ROUTING_KEY: str = "llm.message"

    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Savey API"

    # Dokploy vars

    DOCKER_CONFIG: str = "docker"
    APP_NAME: str = "savey_api"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()