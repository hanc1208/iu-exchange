"""Create User Table

Revision ID: 4cf87b0406f1
Revises:
Create Date: 2020-01-08 23:10:49.195773

"""
from alembic import op
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.schema import Column, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.types import DateTime, Unicode
from sqlalchemy_utils.types.password import PasswordType


# revision identifiers, used by Alembic.

revision = '4cf87b0406f1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user',
        Column('id', UUID(), nullable=False),
        Column('created_at', DateTime(timezone=True), nullable=False),
        Column('email', Unicode(), nullable=False),
        Column('password', PasswordType(), nullable=False),
        PrimaryKeyConstraint('id'),
        UniqueConstraint('email')
    )


def downgrade():
    op.drop_table('user')
