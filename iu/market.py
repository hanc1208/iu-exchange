import decimal

from sqlalchemy.schema import Column
from sqlalchemy.types import Numeric

from .mixin import PrimaryKeyPairMixin
from .orm import Base


class Market(Base, PrimaryKeyPairMixin):
    current_price = Column(
        Numeric(36, 18), nullable=False, default=decimal.Decimal(0),
    )
    maker_fee = Column(Numeric(36, 18), nullable=False)
    taker_fee = Column(Numeric(36, 18), nullable=False)
    minimum_order_amount = Column(Numeric(36, 18), nullable=False)

    __tablename__ = 'market'
