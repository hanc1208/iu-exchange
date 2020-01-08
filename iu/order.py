from __future__ import annotations

import decimal
import enum
import operator
import uuid
from typing import Any, Callable, TypeVar, Union

from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, validates
from sqlalchemy.schema import (
    CheckConstraint, Column, ForeignKey, ForeignKeyConstraint, Index,
    UniqueConstraint,
)
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.expression import asc, case, desc
from sqlalchemy.types import Numeric
from sqlalchemy_enum34 import EnumType
from sqlalchemy_utc.now import utcnow
from sqlalchemy_utc.sqltypes import UtcDateTime
from sqlalchemy_utils.types.uuid import UUIDType
from typeguard import typechecked

from .mixin import PairMixin
from .orm import Base


T = TypeVar('T')


class OrderSide(enum.Enum):
    buy = 'buy'
    sell = 'sell'

    @property
    @typechecked
    def order_op(self) -> Callable:
        """Return matching order of the side."""
        return self.choice(buy=desc, sell=asc)

    @property
    @typechecked
    def compare_op(self) -> Callable[[Any, Any], bool]:
        """Return operator that can be used on sorting orders"""
        return self.choice(buy=operator.ge, sell=operator.le)

    @typechecked
    def __invert__(self) -> OrderSide:
        return self.choice(buy=OrderSide.sell, sell=OrderSide.buy)

    @typechecked
    def choice(self, *, buy: T, sell: T) -> T:
        return buy if self is OrderSide.buy else sell


class Order(Base, PairMixin):
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    created_at = Column(
        UtcDateTime, nullable=False, index=True, default=utcnow(),
    )
    side = Column(EnumType(OrderSide, name='order_side'), nullable=False)
    user_id = Column(
        UUIDType, ForeignKey('user.id'), index=True, nullable=False,
    )
    user = relationship('User')
    market = relationship('Market')
    volume = Column(Numeric(36, 18), nullable=False)
    remaining_volume = Column(Numeric(36, 18), nullable=False)
    price = Column(Numeric(36, 18), nullable=False)
    filled_at = Column(UtcDateTime)
    canceled_at = Column(UtcDateTime)

    __tablename__ = 'order'
    __table_args__ = (
        CheckConstraint(price > 0, 'ck_order_price_positive'),
        CheckConstraint(
            (volume > 0) &
            (remaining_volume >= 0) &
            (remaining_volume <= volume),
            'ck_order_volume',
        ),
        CheckConstraint(
            'base_currency != quote_currency', 'ck_order_currency',
        ),
        CheckConstraint(
            (filled_at.is_(None) & (remaining_volume > 0)) |
            (filled_at.isnot(None) & (remaining_volume == 0)),
            'ck_order_filled',
        ),
        CheckConstraint(
            canceled_at.is_(None) | (remaining_volume > 0),
            'ck_order_canceled',
        ),
        Index(
            'ix_order_book',
            filled_at.is_(None), canceled_at.is_(None),
            'base_currency', 'quote_currency', side, price,
        ),
        ForeignKeyConstraint(
            ('base_currency', 'quote_currency'),
            ('market.base_currency', 'market.quote_currency'),
        ),
        UniqueConstraint(id, 'base_currency', 'quote_currency'),
    )

    @typechecked
    def __repr__(self) -> str:
        return (
            f'side={self.side.value} price={self.price} volume={self.volume}'
        )

    @validates('remaining_volume')
    @typechecked
    def validate_remaining_volume(self, _, remaining_volume: decimal.Decimal):
        if remaining_volume == 0:
            self.filled_at = utcnow()
        return remaining_volume

    @hybrid_property
    @typechecked
    def locking_currency(self) -> str:
        return (
            self.quote_currency if self.side is OrderSide.buy
            else self.base_currency
        )

    @locking_currency.expression
    @typechecked
    def locking_currency(cls) -> ColumnElement:
        return case(
            {cls.side == OrderSide.buy: cls.quote_currency},
            else_=cls.base_currency,
        )

    @hybrid_property
    @typechecked
    def filled_volume(self) -> Union[decimal.Decimal, ColumnElement]:
        return self.volume - self.remaining_volume

    @hybrid_property
    @typechecked
    def locked_amount(self) -> decimal.Decimal:
        return self.volume * (self.price if self.side is OrderSide.buy else 1)

    @locked_amount.expression
    @typechecked
    def locked_amount(cls) -> ColumnElement:
        return (
            cls.volume * case({cls.side == OrderSide.buy: cls.price}, else_=1)
        )

    @hybrid_property
    def remaining_locked_amount(self):
        return self.remaining_volume * (
            self.price if self.side is OrderSide.buy else 1
        )

    @remaining_locked_amount.expression
    @typechecked
    def remaining_locked_amount(cls) -> ColumnElement:
        return (
            cls.remaining_volume *
            case({cls.side == OrderSide.buy: cls.price}, else_=1)
        )

    @hybrid_property
    @typechecked
    def filled(self) -> bool:
        return self.filled_at is not None

    @filled.expression
    @typechecked
    def filled(cls) -> ColumnElement:
        return cls.filled_at.isnot(None)

    @hybrid_property
    @typechecked
    def canceled(self) -> bool:
        return self.canceled_at is not None

    @canceled.expression
    @typechecked
    def canceled(cls) -> ColumnElement:
        return cls.canceled_at.isnot(None)

    @typechecked
    def cancel(self) -> None:
        self.canceled_at = utcnow()

    @hybrid_property
    @typechecked
    def active(self) -> bool:
        return not self.filled and not self.canceled

    @active.expression
    @typechecked
    def active(self) -> ColumnElement:
        return ~self.filled & ~self.canceled
