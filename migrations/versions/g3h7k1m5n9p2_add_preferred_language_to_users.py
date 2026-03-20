"""Add preferred_language to users

Revision ID: g3h7k1m5n9p2
Revises: a1b2c3d4e5f6
Create Date: 2026-02-12 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g3h7k1m5n9p2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add preferred_language column as nullable first
    op.add_column('users', sa.Column('preferred_language', sa.String(), nullable=True))

    # Set English for all existing users
    op.execute("UPDATE users SET preferred_language = 'en' WHERE preferred_language IS NULL")

    # Make column NOT NULL
    op.alter_column('users', 'preferred_language', nullable=False)


def downgrade() -> None:
    op.drop_column('users', 'preferred_language')
