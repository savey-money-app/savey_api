"""Message schemas for responses"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class MessageResponse(BaseModel):
    """Schema for message response"""
    id: UUID
    user_id: UUID
    content: str
    is_user: bool
    had_attachment: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
