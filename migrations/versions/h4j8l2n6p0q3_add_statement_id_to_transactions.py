"""Add statement_id to bulk-imported transactions.

Revision ID: h4j8l2n6p0q3
Revises: g3h7k1m5n9p2
Create Date: 2026-05-22 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h4j8l2n6p0q3"
down_revision: Union[str, None] = "g3h7k1m5n9p2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("statement_id", sa.UUID(), nullable=True))
    op.create_index("ix_transactions_statement_id", "transactions", ["statement_id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_statement_id", table_name="transactions")
    op.drop_column("transactions", "statement_id")
