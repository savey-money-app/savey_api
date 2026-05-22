"""Message model for user chat history (one chat per user)"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from core.database import Base

from core.time import utc_now

class Message(Base):
    """Message model for user's chat history"""
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    content = Column(Text, nullable=False)
    is_user = Column(Boolean, nullable=False, default=True)  # True if user sent, False if AI sent
    had_attachment = Column(Boolean, nullable=False, default=False)
    balance = Column(JSONB, nullable=True)
    hitl_data = Column(JSONB, nullable=True)
    error = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)

    # Relationships
    user = relationship("User", back_populates="messages")
