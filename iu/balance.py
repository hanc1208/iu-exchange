from __future__ import annotations

import decimal
from typing import Union

from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, validates
from sqlalchemy.schema import CheckConstraint, Column, ForeignKey
from sqlalchemy.sql.elements import BinaryExpression
from sqlalchemy.types import Numeric, Unicode
from sqlalchemy_utils.types.uuid import UUIDType
from typeguard import typechecked

from .currency import Currency
from .orm import Base


class Balance(Base):
    user_id = Column(UUIDType, ForeignKey('user.id'), primary_key=True)
    user = relationship('User')
    currency = Column(
        Unicode, ForeignKey(Currency.id), primary_key=True, nullable=False,
    )
    amount = Column(Numeric(36, 18), nullable=False)
    locked_amount = Column(Numeric(36, 18), nullable=False)

    __tablename__ = 'balance'
    __table_args__ = (
        CheckConstraint(
            (amount >= 0) & (locked_amount >= 0) & (amount >= locked_amount),
            'ck_balance_amount',
        ),
    )

    @validates('amount')
    @typechecked
    def validate_amount(
        self, _, amount: decimal.Decimal,
    ) -> decimal.Decimal:
        assert amount >= (self.locked_amount or 0)
        return amount

    @validates('locked_amount')
    @typechecked
    def validate_locked_amount(
        self, _, locked_amount: decimal.Decimal,
    ) -> decimal.Decimal:
        assert 0 <= locked_amount <= (self.amount or 0)
        return locked_amount

    @hybrid_property
    @typechecked
    def usable_amount(self) -> Union[decimal.Decimal, BinaryExpression]:
        return self.amount - self.locked_amount
