"""Message schemas for responses"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional
from schemas.user import UserBalance

class MessageResponse(BaseModel):
    """Schema for message response"""
    id: UUID
    user_id: UUID
    content: str
    is_user: bool
    had_attachment: bool
    hitl_data: Optional[dict] = None
    balance: Optional[UserBalance] = None
    error: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MessageCreate(BaseModel):
    """Schema for creating a new message"""
    user_id: UUID
    content: str
    is_user: bool
    had_attachment: bool
    hitl_data: Optional[dict] = None

    created_at: datetime