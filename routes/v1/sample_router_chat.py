"""PostgreSQL-based conversation routes"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from schemas.pg_schemas import (
    ConversationCreate, ConversationUpdate, ConversationResponse, LastMessageInfo,
    ConversationType, ConfigPatch
)
from services.pg_conversation_services import pg_conversation_service
from services.pg_message_services import pg_message_service
from services import auth_service
from services.entitlements import entitlements, Feature
from core import get_db
from core.exceptions import NoTokensAvailableException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models.pg_conversation_models import Message, Conversation

router = APIRouter(prefix="/conversations-v2", tags=["Conversations V2 (PostgreSQL)"])

@router.post("/", response_model=ConversationResponse)
def create_conversation(
    conversation_data: ConversationCreate,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """
    Create a new conversation

    **Important:** Creating a SUPPORT conversation costs 2 tokens.
    User must have at least 2 tokens to create a support conversation.
    """
    current_user = auth_service.get_current_user(credentials.credentials, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    # Check if this is a support conversation - requires 2 tokens
    if conversation_data.conversation_type == ConversationType.SUPPORT:
        try:
            # Check if user has sufficient tokens (2 tokens required)
            pre_auth = entitlements.authorize_pre(
                db=db,
                user_id=str(current_user.id),
                feature=Feature.SUPPORT_CONVERSATION,
                context={"conversation_type": "support"}
            )
        except NoTokensAvailableException as e:
            raise HTTPException(
                status_code=402,
                detail={
                    "message": e.message,
                    "code": e.error_code,
                    **e.detail
                }
            )
        except PermissionError as e:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient tokens. Support conversations require 2 tokens. {str(e)}"
            )

    # Convert config to dict if provided, otherwise let service create default
    config_dict = None
    if conversation_data.config:
        config_dict = conversation_data.config.model_dump()

    conversation = pg_conversation_service.create_conversation(
        db=db,
        user_id=UUID(str(current_user.id)),
        title=conversation_data.title,
        conversation_type=conversation_data.conversation_type,
        config=config_dict
    )

    # Deduct tokens for support conversation after successful creation
    if conversation_data.conversation_type == ConversationType.SUPPORT:
        try:
            entitlements.authorize_post(
                db=db,
                user_id=str(current_user.id),
                feature=Feature.SUPPORT_CONVERSATION,
                pre_auth=pre_auth,
                final_context={
                    "conversation_id": str(conversation.id),
                    "conversation_type": "support"
                }
            )
            db.commit()  # Commit the token deduction
        except NoTokensAvailableException as e:
            # If token deduction fails, rollback conversation creation
            db.rollback()
            raise HTTPException(
                status_code=402,
                detail={
                    "message": e.message,
                    "code": e.error_code,
                    **e.detail
                }
            )
        except PermissionError as e:
            # If token deduction fails, rollback conversation creation
            db.rollback()
            raise HTTPException(
                status_code=402,
                detail=f"Failed to deduct tokens: {str(e)}"
            )

    return ConversationResponse(
        _id=str(conversation.id),
        user_id=str(conversation.user_id),
        title=conversation.title,
        conversation_type=conversation.conversation_type,
        is_active=conversation.is_active,
        is_archived=conversation.is_archived,
        config=conversation.config,
        related_goal_id=str(conversation.related_goal_id) if conversation.related_goal_id else None,
        message_count=conversation.message_count,
        last_message_at=conversation.last_message_at,
        last_message=None,
        unread_count=conversation.unread_count,
        last_read_message_id=str(conversation.last_read_message_id) if conversation.last_read_message_id else None,
        context_summary=conversation.context_summary,
        tags=conversation.tags,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )

@router.get("/", response_model=List[ConversationResponse])
def get_user_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    conversation_type: ConversationType = Query(ConversationType.CHAT, description="Filter by conversation type"),
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Get conversations for the authenticated user, filtered by type"""
    current_user = auth_service.get_current_user(credentials.credentials, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    conversations = pg_conversation_service.get_user_conversations(
        db=db,
        user_id=UUID(str(current_user.id)),
        skip=skip,
        limit=limit,
        conversation_type=conversation_type
    )

    return [ConversationResponse(**{**conv, "_id": conv["id"]}) for conv in conversations]

@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str = Path(..., description="Conversation ID"),
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Get a specific conversation by ID"""
    current_user = auth_service.get_current_user(credentials.credentials, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    conversation = pg_conversation_service.get_conversation_by_id(
        db=db,
        user_id=UUID(str(current_user.id)),
        conversation_id=UUID(conversation_id)
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get last message info from PostgreSQL
    last_message_info = None
    if conversation.last_message_at and conversation.messages:
        last_message = conversation.messages[0] if conversation.messages else None
        if last_message:
            content_text = ""
            if isinstance(last_message.content, dict):
                content_text = last_message.content.get("text", "")

            last_message_info = LastMessageInfo(
                id=str(last_message.id),
                content=content_text,
                timestamp=last_message.created_at,
                is_user=last_message.is_user
            )

    return ConversationResponse(
        _id=str(conversation.id),
        user_id=str(conversation.user_id),
        title=conversation.title,
        conversation_type=conversation.conversation_type,
        is_active=conversation.is_active,
        is_archived=conversation.is_archived,
        config=conversation.config,
        related_goal_id=str(conversation.related_goal_id) if conversation.related_goal_id else None,
        message_count=conversation.message_count,
        last_message_at=conversation.last_message_at,
        last_message=last_message_info,
        unread_count=conversation.unread_count,
        last_read_message_id=str(conversation.last_read_message_id) if conversation.last_read_message_id else None,
        context_summary=conversation.context_summary,
        tags=conversation.tags,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )

@router.put("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: str = Path(..., description="Conversation ID"),
    conversation_data: ConversationUpdate = None,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Update a conversation"""
    current_user = auth_service.get_current_user(credentials.credentials, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    update_data = conversation_data.dict(exclude_unset=True) if conversation_data else {}

    # Convert config Pydantic object to dict if present
    if "config" in update_data and update_data["config"] is not None:
        # Already a dict from dict() call, but may need nested conversion
        if hasattr(update_data["config"], "model_dump"):
            update_data["config"] = update_data["config"].model_dump()

    conversation = pg_conversation_service.update_conversation(
        db=db,
        user_id=UUID(str(current_user.id)),
        conversation_id=UUID(conversation_id),
        update_data=update_data
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get last message info
    last_message_info = None
    if conversation.last_message_at and conversation.messages:
        last_message = conversation.messages[0] if conversation.messages else None
        if last_message:
            content_text = ""
            if isinstance(last_message.content, dict):
                content_text = last_message.content.get("text", "")

            last_message_info = LastMessageInfo(
                id=str(last_message.id),
                content=content_text,
                timestamp=last_message.created_at,
                is_user=last_message.is_user
            )

    return ConversationResponse(
        _id=str(conversation.id),
        user_id=str(conversation.user_id),
        title=conversation.title,
        conversation_type=conversation.conversation_type,
        is_active=conversation.is_active,
        is_archived=conversation.is_archived,
        config=conversation.config,
        related_goal_id=str(conversation.related_goal_id) if conversation.related_goal_id else None,
        message_count=conversation.message_count,
        last_message_at=conversation.last_message_at,
        last_message=last_message_info,
        unread_count=conversation.unread_count,
        last_read_message_id=str(conversation.last_read_message_id) if conversation.last_read_message_id else None,
        context_summary=conversation.context_summary,
        tags=conversation.tags,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )


@router.patch("/{conversation_id}/config", response_model=ConversationResponse)
def patch_conversation_config(
    conversation_id: str = Path(..., description="Conversation ID"),
    payload: ConfigPatch = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """
    Update conversation configuration using PATCH semantics.

    **Important Notes:**
    - The `kind` field must match the conversation's type (cannot change conversation type)
    - Only provided fields will be updated, others remain unchanged
    - For SUPPORT type: `is_complete` can only be set to True (cannot revert once complete)

    **Example Request Bodies:**
    ```json
    // Mark support session as complete
    {"kind": "support", "is_complete": true}

    // Update journal reference
    {"kind": "support", "report_journal_id": "uuid-here"}

    // Update both
    {"kind": "support", "report_journal_id": "uuid-here", "is_complete": true}
    ```
    """
    current_user = auth_service.get_current_user(credentials.credentials, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    try:
        # Convert payload to dict, excluding unset fields
        config_updates = payload.dict(exclude_unset=True)

        # Validate is_complete logic: can only be set to True
        if "is_complete" in config_updates and config_updates["is_complete"] is False:
            raise HTTPException(
                status_code=422,
                detail="is_complete can only be set to True. Once a support session is complete, it cannot be reverted."
            )

        updated_conversation = pg_conversation_service.patch_conversation_config(
            db=db,
            user_id=UUID(str(current_user.id)),
            conversation_id=UUID(conversation_id),
            config_updates=config_updates
        )

        # Get last message info for the response
        last_message_info = None
        if updated_conversation.last_message_at:
            last_message = (
                db.query(Message)
                .filter(Message.conversation_id == updated_conversation.id)
                .order_by(desc(Message.created_at))
                .limit(1)
                .first()
            )

            if last_message:
                content_text = ""
                if isinstance(last_message.content, dict):
                    content_text = last_message.content.get("text", "")

                last_message_info = LastMessageInfo(
                    id=str(last_message.id),
                    content=content_text,
                    timestamp=last_message.created_at,
                    is_user=last_message.is_user
                )

        return ConversationResponse(
            _id=str(updated_conversation.id),
            user_id=str(updated_conversation.user_id),
            title=updated_conversation.title,
            conversation_type=updated_conversation.conversation_type,
            is_active=updated_conversation.is_active,
            is_archived=updated_conversation.is_archived,
            config=updated_conversation.config,
            related_goal_id=str(updated_conversation.related_goal_id) if updated_conversation.related_goal_id else None,
            message_count=updated_conversation.message_count,
            last_message_at=updated_conversation.last_message_at,
            last_message=last_message_info,
            unread_count=updated_conversation.unread_count,
            last_read_message_id=str(updated_conversation.last_read_message_id) if updated_conversation.last_read_message_id else None,
            context_summary=updated_conversation.context_summary,
            tags=updated_conversation.tags,
            created_at=updated_conversation.created_at,
            updated_at=updated_conversation.updated_at
        )

    except ValueError as e:
        # Handle both "not found" and "type mismatch" errors
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str = Path(..., description="Conversation ID"),
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Delete a conversation"""
    current_user = auth_service.get_current_user(credentials.credentials, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    success = pg_conversation_service.delete_conversation(
        db=db,
        user_id=UUID(str(current_user.id)),
        conversation_id=UUID(conversation_id)
    )

    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"message": "Conversation deleted successfully"}

@router.post("/{conversation_id}/mark-read", response_model=ConversationResponse)
def mark_messages_as_read(
    conversation_id: str = Path(..., description="Conversation ID"),
    last_read_message_id: str = Query(..., description="ID of the last read message"),
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Mark messages as read up to a specific message ID"""
    current_user = auth_service.get_current_user(credentials.credentials, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    conversation = pg_conversation_service.mark_messages_as_read(
        db=db,
        user_id=UUID(str(current_user.id)),
        conversation_id=UUID(conversation_id),
        last_read_message_id=UUID(last_read_message_id)
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get last message info - fetch the most recent message by created_at
    last_message_info = None
    if conversation.last_message_at:
        last_message = (
            db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(desc(Message.created_at))
            .limit(1)
            .first()
        )

        if last_message:
            content_text = ""
            if isinstance(last_message.content, dict):
                content_text = last_message.content.get("text", "")

            last_message_info = LastMessageInfo(
                id=str(last_message.id),
                content=content_text,
                timestamp=last_message.created_at,
                is_user=last_message.is_user
            )

    return ConversationResponse(
        _id=str(conversation.id),
        user_id=str(conversation.user_id),
        title=conversation.title,
        conversation_type=conversation.conversation_type,
        is_active=conversation.is_active,
        is_archived=conversation.is_archived,
        config=conversation.config,
        related_goal_id=str(conversation.related_goal_id) if conversation.related_goal_id else None,
        message_count=conversation.message_count,
        last_message_at=conversation.last_message_at,
        last_message=last_message_info,
        unread_count=conversation.unread_count,
        last_read_message_id=str(conversation.last_read_message_id) if conversation.last_read_message_id else None,
        context_summary=conversation.context_summary,
        tags=conversation.tags,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )

@router.get("/sessions/count", response_model=int)
def get_support_sessions_count(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Get count of support conversations for authenticated user"""
    current_user = auth_service.get_current_user(credentials.credentials, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    count = db.query(Conversation).filter(
        Conversation.user_id == UUID(str(current_user.id)),
        Conversation.conversation_type == ConversationType.SUPPORT
    ).count()

    return count
