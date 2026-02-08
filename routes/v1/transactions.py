"""Transaction management routes"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from core.database import get_db
from schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
    TransactionFilter
)
from services.transaction_service import (
    create_transaction,
    get_transaction_by_id,
    get_user_transactions,
    update_transaction,
    delete_transaction
)
from services.category_service import get_category_by_id
from routes.v1.auth import get_user_internal_or_jwt

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_new_transaction(
    transaction_data: TransactionCreate,
    current_user_id: str = Depends(get_user_internal_or_jwt),
    db: Session = Depends(get_db)
):
    """Create a new transaction"""
    # Validate category exists
    category = get_category_by_id(db, str(transaction_data.category_id))
    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category not found"
        )

    transaction = create_transaction(db, current_user_id, transaction_data)
    return transaction


@router.get("", response_model=List[TransactionResponse])
def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    transaction_type: Optional[str] = None,
    category_id: Optional[UUID] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user_id: str = Depends(get_user_internal_or_jwt),
    db: Session = Depends(get_db)
):
    """Get all transactions for the current user with optional filters"""
    # Build filters
    filters = TransactionFilter(
        transaction_type=transaction_type,
        category_id=category_id,
        start_date=start_date,
        end_date=end_date
    )

    transactions = get_user_transactions(db, current_user_id, filters, skip, limit)
    return transactions


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: str,
    current_user_id: str = Depends(get_user_internal_or_jwt),
    db: Session = Depends(get_db)
):
    """Get a specific transaction by ID"""
    transaction = get_transaction_by_id(db, transaction_id, current_user_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    return transaction


@router.put("/{transaction_id}", response_model=TransactionResponse)
def update_existing_transaction(
    transaction_id: str,
    transaction_data: TransactionUpdate,
    current_user_id: str = Depends(get_user_internal_or_jwt),
    db: Session = Depends(get_db)
):
    """Update a transaction"""
    # Validate category if provided
    if transaction_data.category_id:
        category = get_category_by_id(db, str(transaction_data.category_id))
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category not found"
            )

    transaction = update_transaction(db, transaction_id, current_user_id, transaction_data)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_transaction(
    transaction_id: str,
    current_user_id: str = Depends(get_user_internal_or_jwt),
    db: Session = Depends(get_db)
):
    """Delete a transaction"""
    success = delete_transaction(db, transaction_id, current_user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    return None
