"""Message service for message CRUD operations"""
from sqlalchemy.orm import Session
from models.message import Message
from typing import List, Optional
from schemas.message import MessageCreate


def create_message(
    db: Session,
    message_data: MessageCreate
) -> Message:
    """Create a new message"""
    message = Message(
        user_id=message_data.user_id,
        content=message_data.content,
        is_user=message_data.is_user,
        had_attachment=message_data.had_attachment,
        balance=message_data.balance,
        hitl_data=message_data.hitl_data,
        error=message_data.error,
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
    """
    Return the most recent `limit` messages for a user, oldest-first.

    Query newest-first (DESC) so that `skip` always means "skip the N
    most recent messages" — ideal for chat load-more pagination.
    The slice is then reversed before returning so the client receives
    messages in ascending (oldest→newest) order, ready to display.
    """
    rows = (
        db.query(Message)
        .filter(Message.user_id == user_id)
        .order_by(Message.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def get_message_by_id(db: Session, message_id: str, user_id: str) -> Optional[Message]:
    """Get a specific message by ID for a user"""
    return db.query(Message).filter(
        Message.id == message_id,
        Message.user_id == user_id
    ).first()
