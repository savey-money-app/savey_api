"""Add budget limits to users

Revision ID: f2c6e9a1b4d8
Revises: e4b6d8f2a3c5
Create Date: 2026-02-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f2c6e9a1b4d8'
down_revision = 'e4b6d8f2a3c5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('monthly_limit', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('daily_limit', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('users', 'monthly_limit')
    op.drop_column('users', 'daily_limit')
