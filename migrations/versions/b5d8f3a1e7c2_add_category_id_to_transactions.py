"""Add category_id to transactions and remove category string

Revision ID: b5d8f3a1e7c2
Revises: a3f7e2b9c4d1
Create Date: 2026-02-02 13:00:00.000000

"""
from typing import Sequence, Union
from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b5d8f3a1e7c2'
down_revision: Union[str, None] = 'a3f7e2b9c4d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get connection for data migration
    connection = op.get_bind()

    # Step 1: Add category_id column as nullable first
    op.add_column('transactions', sa.Column('category_id', sa.UUID(), nullable=True))

    # Step 2: Get all unique categories from existing transactions that don't exist in categories table
    existing_categories = connection.execute(
        sa.text("SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL")
    ).fetchall()

    # Step 3: For each unique category string, find or create a category and update transactions
    for (category_name,) in existing_categories:
        if category_name:
            # Check if category exists
            result = connection.execute(
                sa.text("SELECT id FROM categories WHERE title = :title"),
                {"title": category_name}
            ).fetchone()

            if result:
                category_id = result[0]
            else:
                # Create new category
                category_id = str(uuid.uuid4())
                now = datetime.utcnow()
                connection.execute(
                    sa.text("""
                        INSERT INTO categories (id, title, created_at, updated_at)
                        VALUES (:id, :title, :created_at, :updated_at)
                    """),
                    {"id": category_id, "title": category_name, "created_at": now, "updated_at": now}
                )

            # Update transactions with this category
            connection.execute(
                sa.text("UPDATE transactions SET category_id = :category_id WHERE category = :category"),
                {"category_id": category_id, "category": category_name}
            )

    # Step 4: If there are any transactions without category_id, assign a default "Other" category
    result = connection.execute(
        sa.text("SELECT COUNT(*) FROM transactions WHERE category_id IS NULL")
    ).fetchone()

    if result and result[0] > 0:
        # Get or create "Other Expense" category
        other_cat = connection.execute(
            sa.text("SELECT id FROM categories WHERE title = 'Other Expense'")
        ).fetchone()

        if other_cat:
            other_id = other_cat[0]
        else:
            other_id = str(uuid.uuid4())
            now = datetime.utcnow()
            connection.execute(
                sa.text("""
                    INSERT INTO categories (id, title, created_at, updated_at)
                    VALUES (:id, :title, :created_at, :updated_at)
                """),
                {"id": other_id, "title": "Other Expense", "created_at": now, "updated_at": now}
            )

        connection.execute(
            sa.text("UPDATE transactions SET category_id = :category_id WHERE category_id IS NULL"),
            {"category_id": other_id}
        )

    # Step 5: Make category_id NOT NULL
    op.alter_column('transactions', 'category_id', nullable=False)

    # Step 6: Add foreign key constraint
    op.create_foreign_key(
        'fk_transactions_category_id',
        'transactions', 'categories',
        ['category_id'], ['id'],
        ondelete='RESTRICT'
    )

    # Step 7: Drop the old category column
    op.drop_column('transactions', 'category')


def downgrade() -> None:
    # Get connection for data migration
    connection = op.get_bind()

    # Step 1: Add category string column back
    op.add_column('transactions', sa.Column('category', sa.String(), nullable=True))

    # Step 2: Populate category from category_id
    connection.execute(
        sa.text("""
            UPDATE transactions t
            SET category = c.title
            FROM categories c
            WHERE t.category_id = c.id
        """)
    )

    # Step 3: Make category NOT NULL
    op.alter_column('transactions', 'category', nullable=False)

    # Step 4: Drop foreign key
    op.drop_constraint('fk_transactions_category_id', 'transactions', type_='foreignkey')

    # Step 5: Drop category_id column
    op.drop_column('transactions', 'category_id')
