"""Message service for message CRUD and RabbitMQ publishing"""
from sqlalchemy.orm import Session
from models.message import Message
from schemas.message import MessageCreate, MessagePublish
from services.rabbitmq_service import rabbitmq_service
from typing import List, Optional


def create_message(db: Session, user_id: str, message_data: MessageCreate) -> Message:
    """Create a new message"""
    message = Message(
        user_id=user_id,
        content=message_data.content,
        is_user=message_data.is_user
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


async def create_and_publish_message(db: Session, user_id: str, message_data: MessageCreate) -> Message:
    """Create a message and publish it to RabbitMQ"""
    # Create the message in DB
    message = create_message(db, user_id, message_data)

    # Publish to RabbitMQ if it's a user message
    if message.is_user:
        publish_data = MessagePublish(
            user_id=str(message.user_id),
            message_id=str(message.id),
            content=message.content,
            timestamp=message.created_at
        )
        await rabbitmq_service.publish_message(publish_data.model_dump(mode='json'))

    return message


def get_user_messages(
    db: Session,
    user_id: str,
    skip: int = 0,
    limit: int = 50
) -> List[Message]:
    """Get all messages for a user (chat history)"""
    return db.query(Message).filter(
        Message.user_id == user_id
    ).order_by(Message.created_at.asc()).offset(skip).limit(limit).all()


def get_message_by_id(db: Session, message_id: str, user_id: str) -> Optional[Message]:
    """Get a specific message by ID for a user"""
    return db.query(Message).filter(
        Message.id == message_id,
        Message.user_id == user_id
    ).first()
