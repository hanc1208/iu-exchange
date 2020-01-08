"""Create Balance Table

Revision ID: 8270dd906c87
Revises: 898ee8024471
Create Date: 2020-01-08 23:14:46.376891

"""
from alembic import op
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.schema import (
    Column, CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.types import Numeric, Unicode


# revision identifiers, used by Alembic.

revision = '8270dd906c87'
down_revision = '898ee8024471'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'balance',
        Column('user_id', UUID(), nullable=False),
        Column('currency', Unicode(), nullable=False),
        Column('amount', Numeric(precision=36, scale=18), nullable=False),
        Column(
            'locked_amount', Numeric(precision=36, scale=18), nullable=False,
        ),
        CheckConstraint(
            'amount >= 0 AND locked_amount >= 0 AND amount >= locked_amount',
            name='ck_balance_amount'
        ),
        ForeignKeyConstraint(['currency'], ['currency.id'], ),
        ForeignKeyConstraint(['user_id'], ['user.id'], ),
        PrimaryKeyConstraint('user_id', 'currency'),
    )


def downgrade():
    op.drop_table('balance')
