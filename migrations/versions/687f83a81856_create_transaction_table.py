"""Create Transaction Table

Revision ID: 687f83a81856
Revises: 1cc8006d5128
Create Date: 2020-01-09 22:01:02.881682

"""
from alembic import op
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.schema import (
    CheckConstraint, Column, ForeignKeyConstraint, PrimaryKeyConstraint,
)
from sqlalchemy.types import DateTime, Enum, Numeric, Unicode


# revision identifiers, used by Alembic.
revision = '687f83a81856'
down_revision = '1cc8006d5128'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'transaction',
        Column('id', UUID(), nullable=False),
        Column('created_at', DateTime(timezone=True), nullable=False),
        Column(
            'type',
            Enum('blockchain', 'trade', name='transaction_type'),
            nullable=False,
        ),
        Column('user_id', UUID(), nullable=False),
        Column('currency', Unicode(), nullable=False),
        Column('amount', Numeric(precision=36, scale=18), nullable=False),
        CheckConstraint('amount != 0', name='ck_transaction_amount'),
        ForeignKeyConstraint(['currency'], ['currency.id'], ),
        ForeignKeyConstraint(['user_id'], ['user.id'], ),
        PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_transaction_currency'), 'transaction', ['currency'], unique=False,
    )
    op.create_index(
        op.f('ix_transaction_type'), 'transaction', ['type'], unique=False,
    )
    op.create_index(
        op.f('ix_transaction_user_id'), 'transaction', ['user_id'], unique=False,
    )


def downgrade():
    op.drop_index(op.f('ix_transaction_user_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_type'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_currency'), table_name='transaction')
    op.drop_table('transaction')
    op.execute('DROP TYPE transaction_type')
