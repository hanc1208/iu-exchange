"""Create Trade table

Revision ID: 1cc8006d5128
Revises: ed2599cdf1c2
Create Date: 2020-01-08 23:24:20.199393

"""
from alembic import op
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.schema import (
    CheckConstraint, Column, ForeignKeyConstraint, PrimaryKeyConstraint,
)
from sqlalchemy.types import DateTime, Enum, Integer, Numeric, Unicode


# revision identifiers, used by Alembic.
revision = '1cc8006d5128'
down_revision = 'ed2599cdf1c2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'trade',
        Column('id', UUID(), nullable=False),
        Column('created_at', DateTime(timezone=True), nullable=False),
        Column('buy_order_id', UUID(), nullable=False),
        Column('sell_order_id', UUID(), nullable=False),
        Column(
            'side',
            Enum('buy', 'sell', name='order_side', create_type=False),
            nullable=False,
        ),
        Column('volume', Numeric(precision=36, scale=18), nullable=False),
        Column('price', Numeric(precision=36, scale=18), nullable=False),
        Column('index', Integer(), nullable=False),
        Column('base_currency', Unicode(), nullable=False),
        Column('quote_currency', Unicode(), nullable=False),
        CheckConstraint('volume > 0', name='ck_trade_volume'),
        CheckConstraint('price > 0', name='ck_trade_price'),
        CheckConstraint('index >= 0', name='ck_trade_index'),
        ForeignKeyConstraint(['base_currency'], ['currency.id'], ),
        ForeignKeyConstraint(
            ['buy_order_id', 'base_currency', 'quote_currency'],
            ['order.id', 'order.base_currency', 'order.quote_currency'],
        ),
        ForeignKeyConstraint(['buy_order_id'], ['order.id'], ),
        ForeignKeyConstraint(['quote_currency'], ['currency.id'], ),
        ForeignKeyConstraint(
            ['sell_order_id', 'base_currency', 'quote_currency'],
            ['order.id', 'order.base_currency', 'order.quote_currency'],
        ),
        ForeignKeyConstraint(['sell_order_id'], ['order.id'], ),
        PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_trade_created_at'), 'trade', ['created_at'], unique=False,
    )
    op.create_index(
        op.f('ix_trade_sort'), 'trade',
        ['base_currency', 'quote_currency', 'created_at', 'index'],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f('ix_trade_sort'), table_name='trade')
    op.drop_index(op.f('ix_trade_created_at'), table_name='trade')
    op.drop_table('trade')
