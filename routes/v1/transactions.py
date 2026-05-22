"""Transaction management routes"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from core.database import get_db
from core.time import utc_now
from schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
    TransactionFilter,
    TransactionWithBalance,
    BulkTransactionWithBalance,
    BulkDeleteWithBalance,
    DeleteWithBalance,
)
from services.transaction_service import (
    create_transaction,
    get_transaction_by_id,
    get_user_transactions,
    update_transaction,
    delete_transaction,
    delete_latest_transaction,
    delete_latest_statement_transactions,
    calculate_user_balance,
)
from services.category_service import get_category_by_id, get_category_by_title, create_category
from services.user_service import get_user_by_id
from schemas.category import CategoryCreate
from routes.v1.auth import get_user_internal_or_jwt

router = APIRouter(prefix="/transactions", tags=["Transactions"])


def _calculate_current_balance(db: Session, user_id: str):
    user = get_user_by_id(db, user_id)
    return calculate_user_balance(
        db,
        user_id,
        monthly_limit=user.monthly_limit if user else None,
        daily_limit=user.daily_limit if user else None,
    )


@router.post("", response_model=TransactionWithBalance, status_code=status.HTTP_201_CREATED)
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
    balance = _calculate_current_balance(db, current_user_id)
    return TransactionWithBalance(transaction=transaction, balance=balance)


@router.get("", response_model=List[TransactionResponse])
def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=2000),
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


class BulkTransactionItem(BaseModel):
    amount: float
    category: str
    description: Optional[str] = None
    transaction_type: Optional[str] = None
    date: Optional[str] = None


class BulkTransactionCreate(BaseModel):
    transactions: List[BulkTransactionItem]
    statement_date: Optional[str] = None


class BulkTransactionResponse(BaseModel):
    created_count: int
    statement_id: Optional[str] = None


def _resolve_or_create_category(db: Session, category_name: str) -> UUID:
    """Look up category by name, creating it if it doesn't exist."""
    cat = get_category_by_title(db, category_name)
    if not cat:
        cat = create_category(db, CategoryCreate(title=category_name))
    return cat.id


@router.post("/bulk", response_model=BulkTransactionWithBalance, status_code=status.HTTP_201_CREATED)
def create_bulk_transactions(
    payload: BulkTransactionCreate,
    current_user_id: str = Depends(get_user_internal_or_jwt),
    db: Session = Depends(get_db),
):
    """Create multiple transactions from a bank statement (bulk import)."""
    import uuid as _uuid
    statement_id = _uuid.uuid4()
    created = 0

    for item in payload.transactions:
        category_id = _resolve_or_create_category(db, item.category)

        # Determine transaction_type from sign if not provided
        if item.transaction_type:
            tx_type = item.transaction_type
        else:
            tx_type = "income" if item.amount >= 0 else "expense"

        # Parse date
        if item.date:
            try:
                tx_date = datetime.fromisoformat(item.date).date()
            except ValueError:
                tx_date = utc_now().date()
        else:
            tx_date = utc_now().date()

        tx_data = TransactionCreate(
            amount=abs(item.amount),
            category_id=category_id,
            description=item.description,
            transaction_type=tx_type,
            date=tx_date,
        )
        create_transaction(db, current_user_id, tx_data, statement_id=statement_id)
        created += 1

    balance = _calculate_current_balance(db, current_user_id)
    return BulkTransactionWithBalance(created_count=created, statement_id=str(statement_id), balance=balance)


@router.delete("/last", response_model=DeleteWithBalance, status_code=status.HTTP_200_OK)
def delete_last_transaction(
    current_user_id: str = Depends(get_user_internal_or_jwt),
    db: Session = Depends(get_db),
):
    """Delete the current user's most recently created transaction."""
    if not delete_latest_transaction(db, current_user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    return DeleteWithBalance(balance=_calculate_current_balance(db, current_user_id))


@router.delete(
    "/last-statement",
    response_model=BulkDeleteWithBalance,
    status_code=status.HTTP_200_OK,
)
def delete_last_statement_transactions(
    current_user_id: str = Depends(get_user_internal_or_jwt),
    db: Session = Depends(get_db),
):
    """Delete the current user's most recent statement-import batch."""
    deleted_count = delete_latest_statement_transactions(db, current_user_id)
    if not deleted_count:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement transactions not found",
        )

    return BulkDeleteWithBalance(
        deleted_count=deleted_count,
        balance=_calculate_current_balance(db, current_user_id),
    )


@router.delete("/{transaction_id}", response_model=DeleteWithBalance, status_code=status.HTTP_200_OK)
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

    return DeleteWithBalance(balance=_calculate_current_balance(db, current_user_id))
