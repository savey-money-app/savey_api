"""Add categories table with seed data

Revision ID: a3f7e2b9c4d1
Revises: cb6a6a53d8d1
Create Date: 2026-02-02 12:00:00.000000

"""
from typing import Sequence, Union
from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7e2b9c4d1'
down_revision: Union[str, None] = 'cb6a6a53d8d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default categories for budget management
DEFAULT_CATEGORIES = [
    # Expense categories
    "Food & Dining",
    "Groceries",
    "Transportation",
    "Fuel",
    "Education",
    "Clothing",
    "Entertainment",
    "Healthcare",
    "Housing & Rent",
    "Utilities",
    "Shopping",
    "Personal Care",
    "Travel",
    "Subscriptions",
    "Insurance",
    "Gifts & Donations",
    "Other Expense",
    # Income categories
    "Salary",
    "Freelance",
    "Passive Income",
    "Investments",
    "Business Income",
    "Gifts Received",
    "Refunds",
    "Bonus",
    "Other Income",
]


def upgrade() -> None:
    # Create categories table
    op.create_table('categories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('title')
    )

    # Seed default categories
    categories_table = sa.table('categories',
        sa.column('id', sa.UUID()),
        sa.column('title', sa.String()),
        sa.column('created_at', sa.DateTime()),
        sa.column('updated_at', sa.DateTime()),
    )

    now = datetime.utcnow()
    op.bulk_insert(categories_table, [
        {
            'id': str(uuid.uuid4()),
            'title': title,
            'created_at': now,
            'updated_at': now,
        }
        for title in DEFAULT_CATEGORIES
    ])


def downgrade() -> None:
    op.drop_table('categories')
