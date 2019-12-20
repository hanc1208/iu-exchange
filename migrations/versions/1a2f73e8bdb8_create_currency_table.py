"""Create currency table

Revision ID: 1a2f73e8bdb8
Revises: 4cf87b0406f1
Create Date: 2019-12-20 12:54:08.696581

"""
from alembic import op
from sqlalchemy.schema import CheckConstraint, Column, PrimaryKeyConstraint
from sqlalchemy.types import Integer, Numeric, Unicode


# revision identifiers, used by Alembic.
revision = '1a2f73e8bdb8'
down_revision = '4cf87b0406f1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'currency',
        Column('id', Unicode(), nullable=False),
        Column('name', Unicode(), nullable=False),
        Column('decimals', Integer(), nullable=False),
        Column('confirmations', Integer(), nullable=False),
        Column(
            'minimum_deposit_amount',
            Numeric(precision=36, scale=18),
            nullable=False,
        ),
        Column(
            'minimum_withdrawal_amount',
            Numeric(precision=36, scale=18),
            nullable=False,
        ),
        Column(
            'withdrawal_fee',
            Numeric(precision=36, scale=18),
            nullable=False,
        ),
        Column('latest_synced_block_number', Integer(), nullable=False),
        CheckConstraint('decimals >= 0', name='ck_currency_decimals'),
        CheckConstraint('id = upper(id)', name='ck_currency_id_upper'),
        PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('currency')
