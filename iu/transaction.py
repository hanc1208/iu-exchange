import enum
import uuid

from sqlalchemy.orm import relationship
from sqlalchemy.schema import CheckConstraint, Column, ForeignKey
from sqlalchemy.types import Numeric, Unicode
from sqlalchemy_enum34 import EnumType
from sqlalchemy_utc.now import utcnow
from sqlalchemy_utc.sqltypes import UtcDateTime
from sqlalchemy_utils.types.uuid import UUIDType

from .orm import Base


class TransactionType(enum.Enum):
    blockchain = 'blockchain'
    trade = 'trade'


class Transaction(Base):
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow())
    type = Column(
        EnumType(TransactionType, name='transaction_type'),
        nullable=False, index=True,
    )
    user_id = Column(
        UUIDType, ForeignKey('user.id'), index=True, nullable=False,
    )
    user = relationship('User')
    currency = Column(
        Unicode, ForeignKey('currency.id'), index=True, nullable=False,
    )
    amount = Column(Numeric(36, 18), nullable=False)

    __tablename__ = 'transaction'
    __table_args__ = (
        CheckConstraint(amount != 0, 'ck_transaction_amount'),
    )
    __mapper_args__ = {
        'polymorphic_on': type,
        'polymorphic_identity': None,
        'with_polymorphic': '*',
    }
