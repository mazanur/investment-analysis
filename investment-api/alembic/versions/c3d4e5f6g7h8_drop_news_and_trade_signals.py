"""drop news and trade_signals tables

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-03-08 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, Sequence[str]] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop trade_signals and news tables."""
    op.drop_table('trade_signals')
    op.drop_table('news')

    # Drop enums only used by these tables
    for enum_name in [
        'signalstatusenum', 'positionsizeenum', 'directionenum',
        'signalenum', 'actionenum', 'strengthenum',
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")


def downgrade() -> None:
    """Recreate news and trade_signals tables."""
    op.create_table('news',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('sector_id', sa.Integer(), nullable=True),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=200), nullable=True),
        sa.Column('impact', sa.Enum('positive', 'negative', 'mixed', 'neutral', name='impactenum'), nullable=True),
        sa.Column('strength', sa.Enum('high', 'medium', 'low', name='strengthenum', create_type=True), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('action', sa.Enum('buy', 'hold', 'sell', name='actionenum', create_type=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['sector_id'], ['sectors.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('trade_signals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('news_id', sa.Integer(), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('signal', sa.Enum('buy', 'skip', name='signalenum', create_type=True), nullable=False),
        sa.Column('direction', sa.Enum('long-positive', 'long-oversold', 'skip', name='directionenum', create_type=True), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('entry_price', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('entry_condition', sa.String(length=500), nullable=True),
        sa.Column('take_profit', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('stop_loss', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('time_limit_days', sa.Integer(), nullable=True),
        sa.Column('expected_return_pct', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('risk_reward', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('position_size', sa.Enum('full', 'half', 'skip', name='positionsizeenum', create_type=True), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('active', 'closed', 'expired', name='signalstatusenum', create_type=True), nullable=False),
        sa.Column('result_pct', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['news_id'], ['news.id']),
        sa.PrimaryKeyConstraint('id')
    )
