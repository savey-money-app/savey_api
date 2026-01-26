"""Message schemas for requests and responses"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class MessageCreate(BaseModel):
    """Schema for creating a new message"""
    content: str
    is_user: bool = True


class MessageResponse(BaseModel):
    """Schema for message response"""
    id: str
    user_id: str
    content: str
    is_user: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessagePublish(BaseModel):
    """Schema for publishing message to RabbitMQ"""
    user_id: str
    message_id: str
    content: str
    timestamp: datetime
