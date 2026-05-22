"""Transaction service for transaction CRUD and filtering operations"""
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from models.transaction import Transaction, TransactionType
from schemas.transaction import TransactionCreate, TransactionUpdate, TransactionFilter, UserBalance
from typing import List, Optional
from uuid import UUID


def create_transaction(
    db: Session,
    user_id: str,
    transaction_data: TransactionCreate,
    statement_id: Optional[UUID] = None,
) -> Transaction:
    """Create a new transaction"""
    transaction = Transaction(
        user_id=user_id,
        statement_id=statement_id,
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

    return query.order_by(Transaction.date.desc(), Transaction.created_at.desc()).offset(skip).limit(limit).all()


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


def delete_latest_transaction(db: Session, user_id: str) -> bool:
    """Delete the user's most recently created transaction."""
    transaction = db.query(Transaction).filter(
        Transaction.user_id == user_id
    ).order_by(Transaction.created_at.desc()).first()
    if not transaction:
        return False

    db.delete(transaction)
    db.commit()
    return True


def delete_latest_statement_transactions(db: Session, user_id: str) -> int:
    """Delete the user's most recent statement-import transaction batch."""
    latest = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.statement_id.is_not(None),
    ).order_by(Transaction.created_at.desc()).first()
    if not latest:
        return 0

    transactions = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.statement_id == latest.statement_id,
    ).all()
    for transaction in transactions:
        db.delete(transaction)

    db.commit()
    return len(transactions)


def calculate_user_balance(
    db: Session,
    user_id: str,
    monthly_limit: Optional[int] = None,
    daily_limit: Optional[int] = None,
) -> UserBalance:
    """Compute the user's current balance, monthly spending and daily spending."""
    today = date.today()
    first_of_month = today.replace(day=1)

    # Total balance: sum(income) - sum(expense)
    income_total = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_type == TransactionType.INCOME,
    ).scalar()

    expense_total = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_type == TransactionType.EXPENSE,
    ).scalar()

    # Monthly spending (current calendar month)
    monthly_spending = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_type == TransactionType.EXPENSE,
        Transaction.date >= first_of_month,
    ).scalar()

    # Daily spending (today)
    daily_spending = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_type == TransactionType.EXPENSE,
        Transaction.date == today,
    ).scalar()

    return UserBalance(
        balance=float(income_total) - float(expense_total),
        monthly_spending=float(monthly_spending),
        monthly_limit=float(monthly_limit or 0),
        daily_spending=float(daily_spending),
        daily_limit=float(daily_limit or 0),
    )
