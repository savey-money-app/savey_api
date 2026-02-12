"""Message service for message CRUD operations"""
from sqlalchemy.orm import Session
from models.message import Message
from typing import List, Optional


def create_message(
    db: Session,
    user_id: str,
    content: str,
    is_user: bool,
    had_attachment: bool = False,
) -> Message:
    """Create a new message"""
    message = Message(
        user_id=user_id,
        content=content,
        is_user=is_user,
        had_attachment=had_attachment,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
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
