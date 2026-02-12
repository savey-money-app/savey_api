"""Add had_attachment to messages

Revision ID: e4b6d8f2a3c5
Revises: d2a4f6c8e1b5
Create Date: 2026-02-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4b6d8f2a3c5'
down_revision: Union[str, None] = 'd2a4f6c8e1b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add had_attachment column with server default for existing rows
    op.add_column('messages', sa.Column('had_attachment', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    # Drop server default after backfill (keep only Python-side default)
    op.alter_column('messages', 'had_attachment', server_default=None)


def downgrade() -> None:
    op.drop_column('messages', 'had_attachment')
