"""news and trade_signals id to bigint

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-08 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str]] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change news.id, trade_signals.id, trade_signals.news_id to BIGINT."""
    op.drop_constraint('trade_signals_news_id_fkey', 'trade_signals', type_='foreignkey')

    op.alter_column('news', 'id',
                     existing_type=sa.Integer(),
                     type_=sa.BigInteger(),
                     existing_nullable=False)

    op.alter_column('trade_signals', 'id',
                     existing_type=sa.Integer(),
                     type_=sa.BigInteger(),
                     existing_nullable=False)

    op.alter_column('trade_signals', 'news_id',
                     existing_type=sa.Integer(),
                     type_=sa.BigInteger(),
                     existing_nullable=True)

    op.create_foreign_key('trade_signals_news_id_fkey', 'trade_signals', 'news',
                          ['news_id'], ['id'])


def downgrade() -> None:
    """Revert to INTEGER."""
    op.drop_constraint('trade_signals_news_id_fkey', 'trade_signals', type_='foreignkey')

    op.alter_column('trade_signals', 'news_id',
                     existing_type=sa.BigInteger(),
                     type_=sa.Integer(),
                     existing_nullable=True)

    op.alter_column('trade_signals', 'id',
                     existing_type=sa.BigInteger(),
                     type_=sa.Integer(),
                     existing_nullable=False)

    op.alter_column('news', 'id',
                     existing_type=sa.BigInteger(),
                     type_=sa.Integer(),
                     existing_nullable=False)

    op.create_foreign_key('trade_signals_news_id_fkey', 'trade_signals', 'news',
                          ['news_id'], ['id'])
