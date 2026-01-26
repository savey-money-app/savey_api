"""RabbitMQ service for publishing messages to the LLM service"""
import json
import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
from typing import Optional
from core.config import settings
import logging

logger = logging.getLogger(__name__)


class RabbitMQService:
    """Service for managing RabbitMQ connections and message publishing"""

    def __init__(self):
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None

    async def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            self.connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self.channel = await self.connection.channel()

            # Declare exchange
            self.exchange = await self.channel.declare_exchange(
                settings.RABBITMQ_EXCHANGE,
                ExchangeType.TOPIC,
                durable=True
            )

            # Declare queue
            queue = await self.channel.declare_queue(
                settings.RABBITMQ_QUEUE,
                durable=True
            )

            # Bind queue to exchange
            await queue.bind(self.exchange, routing_key=settings.RABBITMQ_ROUTING_KEY)

            logger.info("Successfully connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def disconnect(self):
        """Close RabbitMQ connection"""
        if self.connection:
            await self.connection.close()
            logger.info("Disconnected from RabbitMQ")

    async def publish_message(self, message_data: dict):
        """Publish a message to RabbitMQ"""
        if not self.exchange:
            raise RuntimeError("RabbitMQ not connected. Call connect() first.")

        try:
            message_body = json.dumps(message_data).encode()
            message = Message(
                message_body,
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json"
            )

            await self.exchange.publish(
                message,
                routing_key=settings.RABBITMQ_ROUTING_KEY
            )

            logger.info(f"Published message to RabbitMQ: {message_data.get('message_id')}")
        except Exception as e:
            logger.error(f"Failed to publish message to RabbitMQ: {e}")
            raise


# Global instance
rabbitmq_service = RabbitMQService()
