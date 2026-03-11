"""add trigger_tags to catalysts

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-03-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "d4e5f6g7h8i9"
down_revision: str = "c3d4e5f6g7h8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("catalysts", sa.Column("trigger_tags", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("catalysts", "trigger_tags")
