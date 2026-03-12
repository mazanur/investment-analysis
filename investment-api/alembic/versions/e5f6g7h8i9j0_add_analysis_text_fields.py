"""add business_model, thesis, scenarios to companies

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-03-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6g7h8i9j0"
down_revision: str = "d4e5f6g7h8i9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("business_model", sa.Text(), nullable=True))
    op.add_column("companies", sa.Column("thesis", sa.Text(), nullable=True))
    op.add_column("companies", sa.Column("scenarios", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "scenarios")
    op.drop_column("companies", "thesis")
    op.drop_column("companies", "business_model")