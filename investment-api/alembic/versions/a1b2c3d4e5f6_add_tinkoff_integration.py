"""add tinkoff integration

Revision ID: a1b2c3d4e5f6
Revises: 85d1cad0af6c
Create Date: 2026-03-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '85d1cad0af6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Tinkoff fields to companies + order_book_snapshots + intraday_candles tables."""
    # Add Tinkoff fields to companies
    op.add_column('companies', sa.Column('figi', sa.String(length=12), nullable=True))
    op.add_column('companies', sa.Column('tinkoff_uid', sa.String(length=50), nullable=True))
    op.add_column('companies', sa.Column('lot_size', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_companies_figi'), 'companies', ['figi'], unique=False)

    # Create order_book_snapshots table
    op.create_table('order_book_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('best_bid', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('best_ask', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('spread_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('depth', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'timestamp', name='uq_orderbook_company_ts'),
    )

    # Create intraday_candles table
    op.create_table('intraday_candles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('interval', sa.String(length=10), nullable=False),
        sa.Column('open', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('high', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('low', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('close', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('volume', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'timestamp', 'interval', name='uq_intraday_company_ts_interval'),
    )


def downgrade() -> None:
    """Remove Tinkoff integration tables and columns."""
    op.drop_table('intraday_candles')
    op.drop_table('order_book_snapshots')
    op.drop_index(op.f('ix_companies_figi'), table_name='companies')
    op.drop_column('companies', 'lot_size')
    op.drop_column('companies', 'tinkoff_uid')
    op.drop_column('companies', 'figi')
