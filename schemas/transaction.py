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


class UserBalance(BaseModel):
    """Computed user balance summary"""
    balance: float
    monthly_spending: float
    monthly_limit: float = 0.0
    daily_spending: float
    daily_limit: float = 0.0


class TransactionWithBalance(BaseModel):
    """Transaction response with updated balance"""
    transaction: TransactionResponse
    balance: UserBalance


class BulkTransactionWithBalance(BaseModel):
    """Bulk transaction response with updated balance"""
    created_count: int
    statement_id: Optional[str] = None
    balance: UserBalance


class BulkDeleteWithBalance(BaseModel):
    """Response after deleting a statement transaction batch"""
    deleted_count: int
    balance: UserBalance


class DeleteWithBalance(BaseModel):
    """Response after deleting a transaction"""
    balance: UserBalance
