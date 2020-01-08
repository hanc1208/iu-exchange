"""Create Order Table

Revision ID: ed2599cdf1c2
Revises: 8270dd906c87
Create Date: 2020-01-08 23:20:51.610443

"""
import sqlalchemy_enum34
from alembic import op
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.schema import (
    Column, CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.types import DateTime, Enum, Numeric, Unicode


# revision identifiers, used by Alembic.
revision = 'ed2599cdf1c2'
down_revision = '8270dd906c87'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'order',
        Column('id', UUID(), nullable=False),
        Column('created_at', DateTime(timezone=True), nullable=False),
        Column('side', Enum('buy', 'sell', name='order_side'), nullable=False),
        Column('user_id', UUID(), nullable=False),
        Column('volume', Numeric(precision=36, scale=18), nullable=False),
        Column(
            'remaining_volume', Numeric(precision=36, scale=18), nullable=False,
        ),
        Column('price', Numeric(precision=36, scale=18), nullable=False),
        Column('filled_at', DateTime(timezone=True), nullable=True),
        Column('canceled_at', DateTime(timezone=True), nullable=True),
        Column('base_currency', Unicode(), nullable=False),
        Column('quote_currency', Unicode(), nullable=False),
        CheckConstraint('price > 0', name='ck_order_price_positive'),
        CheckConstraint(
            'volume > 0 AND '
            'remaining_volume >= 0 AND '
            'remaining_volume <= volume',
            name='ck_order_volume',
        ),
        CheckConstraint(
            'base_currency != quote_currency', name='ck_order_currency',
        ),
        CheckConstraint(
            'filled_at IS NULL OR remaining_volume = 0',
            name='ck_order_filled',
        ),
        CheckConstraint(
            'canceled_at IS NULL OR remaining_volume > 0',
            name='ck_order_canceled',
        ),
        ForeignKeyConstraint(
            ['base_currency', 'quote_currency'],
            ['market.base_currency', 'market.quote_currency'],
        ),
        ForeignKeyConstraint(['base_currency'], ['currency.id'], ),
        ForeignKeyConstraint(['quote_currency'], ['currency.id'], ),
        ForeignKeyConstraint(['user_id'], ['user.id'], ),
        PrimaryKeyConstraint('id'),
        UniqueConstraint('id', 'base_currency', 'quote_currency'),
    )
    op.create_index(
        op.f('ix_order_created_at'), 'order', ['created_at'], unique=False,
    )
    op.create_index(
        op.f('ix_order_user_id'), 'order', ['user_id'], unique=False,
    )


def downgrade():
    op.drop_index(op.f('ix_order_user_id'), table_name='order')
    op.drop_index(op.f('ix_order_created_at'), table_name='order')
    op.drop_table('order')
    op.execute('DROP TYPE "order_side"')
