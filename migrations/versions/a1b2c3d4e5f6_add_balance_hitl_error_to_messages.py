"""add balance, hitl_data, error to messages

Revision ID: a1b2c3d4e5f6
Revises: f2c6e9a1b4d8
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'a1b2c3d4e5f6'
down_revision = 'f2c6e9a1b4d8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('messages', sa.Column('balance', JSONB, nullable=True))
    op.add_column('messages', sa.Column('hitl_data', JSONB, nullable=True))
    op.add_column('messages', sa.Column('error', sa.String, nullable=True))


def downgrade():
    op.drop_column('messages', 'balance')
    op.drop_column('messages', 'hitl_data')
    op.drop_column('messages', 'error')
