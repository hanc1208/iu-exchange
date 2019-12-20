"""Create Market Table

Revision ID: 898ee8024471
Revises: 1a2f73e8bdb8
Create Date: 2019-12-20 21:50:06.407900

"""
from alembic import op
from sqlalchemy.schema import (
    Column, ForeignKeyConstraint, PrimaryKeyConstraint,
)
from sqlalchemy.types import Numeric, Unicode


# revision identifiers, used by Alembic.
revision = '898ee8024471'
down_revision = '1a2f73e8bdb8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'market',
        Column('current_price', Numeric(precision=36, scale=18), nullable=False),
        Column('maker_fee', Numeric(precision=36, scale=18), nullable=False),
        Column('taker_fee', Numeric(precision=36, scale=18), nullable=False),
        Column('minimum_order_amount', Numeric(precision=36, scale=18), nullable=False),
        Column('base_currency', Unicode(), nullable=False),
        Column('quote_currency', Unicode(), nullable=False),
        ForeignKeyConstraint(['base_currency'], ['currency.id'], ),
        ForeignKeyConstraint(['quote_currency'], ['currency.id'], ),
        PrimaryKeyConstraint('base_currency', 'quote_currency'),
    )


def downgrade():
    op.drop_table('market')
