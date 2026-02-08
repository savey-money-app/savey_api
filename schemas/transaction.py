"""Transaction schemas for requests and responses"""
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime, date
from typing import Optional
from uuid import UUID
from models.transaction import TransactionType
from schemas.category import CategoryResponse


class TransactionCreate(BaseModel):
    """Schema for creating a new transaction"""
    amount: Decimal = Field(..., gt=0, description="Transaction amount (must be positive)")
    category_id: UUID
    description: Optional[str] = None
    transaction_type: TransactionType
    date: date


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction"""
    amount: Optional[Decimal] = Field(None, gt=0)
    category_id: Optional[UUID] = None
    description: Optional[str] = None
    transaction_type: Optional[TransactionType] = None
    date: Optional[date] = None


class TransactionResponse(BaseModel):
    """Schema for transaction response"""
    id: UUID
    user_id: UUID
    category_id: UUID
    category: CategoryResponse
    amount: Decimal
    description: Optional[str] = None
    transaction_type: TransactionType
    date: date
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionFilter(BaseModel):
    """Schema for filtering transactions"""
    transaction_type: Optional[TransactionType] = None
    category_id: Optional[UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
