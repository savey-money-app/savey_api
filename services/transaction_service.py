"""Transaction service for transaction CRUD and filtering operations"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from models.transaction import Transaction
from schemas.transaction import TransactionCreate, TransactionUpdate, TransactionFilter
from typing import List, Optional


def create_transaction(db: Session, user_id: str, transaction_data: TransactionCreate) -> Transaction:
    """Create a new transaction"""
    transaction = Transaction(
        user_id=user_id,
        **transaction_data.model_dump()
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def get_transaction_by_id(db: Session, transaction_id: str, user_id: str) -> Optional[Transaction]:
    """Get transaction by ID for a specific user"""
    return db.query(Transaction).filter(
        and_(Transaction.id == transaction_id, Transaction.user_id == user_id)
    ).first()


def get_user_transactions(
    db: Session,
    user_id: str,
    filters: Optional[TransactionFilter] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Transaction]:
    """Get all transactions for a user with optional filtering"""
    query = db.query(Transaction).filter(Transaction.user_id == user_id)

    # Apply filters if provided
    if filters:
        if filters.transaction_type:
            query = query.filter(Transaction.transaction_type == filters.transaction_type)
        if filters.category_id:
            query = query.filter(Transaction.category_id == filters.category_id)
        if filters.start_date:
            query = query.filter(Transaction.date >= filters.start_date)
        if filters.end_date:
            query = query.filter(Transaction.date <= filters.end_date)
        if filters.min_amount:
            query = query.filter(Transaction.amount >= filters.min_amount)
        if filters.max_amount:
            query = query.filter(Transaction.amount <= filters.max_amount)

    return query.order_by(Transaction.date.desc()).offset(skip).limit(limit).all()


def update_transaction(
    db: Session,
    transaction_id: str,
    user_id: str,
    transaction_data: TransactionUpdate
) -> Optional[Transaction]:
    """Update a transaction"""
    transaction = get_transaction_by_id(db, transaction_id, user_id)
    if not transaction:
        return None

    update_data = transaction_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(transaction, field, value)

    db.commit()
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, transaction_id: str, user_id: str) -> bool:
    """Delete a transaction"""
    transaction = get_transaction_by_id(db, transaction_id, user_id)
    if not transaction:
        return False

    db.delete(transaction)
    db.commit()
    return True
