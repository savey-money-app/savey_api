"""Add currency to users

Revision ID: c7e9a4b2f8d3
Revises: b5d8f3a1e7c2
Create Date: 2026-02-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e9a4b2f8d3'
down_revision: Union[str, None] = 'b5d8f3a1e7c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add currency column as nullable first
    op.add_column('users', sa.Column('currency', sa.String(3), nullable=True))

    # Set default USD for existing users
    op.execute("UPDATE users SET currency = 'USD' WHERE currency IS NULL")

    # Make column NOT NULL
    op.alter_column('users', 'currency', nullable=False)


def downgrade() -> None:
    op.drop_column('users', 'currency')
