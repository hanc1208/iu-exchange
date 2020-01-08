from __future__ import annotations

import enum
import operator
from typing import Any, Callable, TypeVar

from sqlalchemy.sql.expression import asc, desc
from typeguard import typechecked


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
