"""Transaction model for money tracking"""
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Enum as SQLEnum, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from enum import Enum as PyEnum
from core.database import Base
from core.time import utc_now


class TransactionType(str, PyEnum):
    """Transaction type enum"""
    INCOME = "income"
    EXPENSE = "expense"


class Transaction(Base):
    """Transaction model for tracking income and expenses"""
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    amount = Column(Numeric(precision=10, scale=2), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    statement_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    description = Column(String, nullable=True)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    date = Column(Date, nullable=False)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="transactions")
    category = relationship("Category", lazy="joined")
