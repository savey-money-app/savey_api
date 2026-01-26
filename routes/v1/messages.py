"""Message/chat routes for user message history"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db
from schemas.message import MessageCreate, MessageResponse
from services.message_service import create_and_publish_message, get_user_messages
from routes.v1.auth import get_current_user

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    message_data: MessageCreate,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new message and publish to RabbitMQ if it's a user message.
    User messages will be sent to the LLM service for processing.
    """
    message = await create_and_publish_message(db, current_user_id, message_data)
    return message


@router.get("", response_model=List[MessageResponse])
def list_messages(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat history for the current user"""
    messages = get_user_messages(db, current_user_id, skip, limit)
    return messages
