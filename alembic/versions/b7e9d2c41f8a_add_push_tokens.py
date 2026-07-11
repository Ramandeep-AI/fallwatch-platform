"""add push_tokens

Revision ID: b7e9d2c41f8a
Revises: 82ca56e6252e
Create Date: 2026-07-11 11:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e9d2c41f8a'
down_revision: Union[str, None] = '82ca56e6252e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('push_tokens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token', sa.String(length=200), nullable=False),
    sa.Column('device_name', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token')
    )


def downgrade() -> None:
    op.drop_table('push_tokens')
