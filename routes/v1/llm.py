"""Mock LLM endpoint that publishes messages to RabbitMQ"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from core.database import get_db
from schemas.message import MessageCreate, MessagePublish
from services.rabbitmq_service import rabbitmq_service
from routes.v1.auth import get_current_user
from datetime import datetime
import uuid

router = APIRouter(prefix="/llm", tags=["LLM Mock"])


@router.post("/messages", status_code=status.HTTP_202_ACCEPTED)
async def mock_llm_message(
    message_data: MessageCreate,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mock LLM endpoint that publishes a message to RabbitMQ.
    This is for testing the RabbitMQ integration without the actual LLM service.
    Returns 202 Accepted to indicate the message has been queued for processing.
    """
    # Create a publish payload
    publish_data = MessagePublish(
        user_id=current_user_id,
        message_id=str(uuid.uuid4()),
        content=message_data.content,
        timestamp=datetime.utcnow()
    )

    # Publish to RabbitMQ
    await rabbitmq_service.publish_message(publish_data.model_dump(mode='json'))

    return {
        "status": "accepted",
        "message": "Message queued for LLM processing",
        "message_id": publish_data.message_id
    }
