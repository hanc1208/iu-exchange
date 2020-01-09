"""Create TradeTransaction Table

Revision ID: a3772c7ab76c
Revises: 687f83a81856
Create Date: 2020-01-09 23:01:07.148748

"""
from alembic import op
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.schema import (
    Column, ForeignKeyConstraint, PrimaryKeyConstraint,
)


# revision identifiers, used by Alembic.
revision = 'a3772c7ab76c'
down_revision = '687f83a81856'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'trade_transaction',
        Column('id', UUID(), nullable=False),
        Column('trade_id', UUID(), nullable=True),
        ForeignKeyConstraint(['id'], ['transaction.id'], ),
        ForeignKeyConstraint(['trade_id'], ['trade.id'], ),
        PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('trade_transaction')
