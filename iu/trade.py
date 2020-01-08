import uuid

from sqlalchemy import CheckConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column, ForeignKey, ForeignKeyConstraint, Index
from sqlalchemy.types import Integer, Numeric
from sqlalchemy_enum34 import EnumType
from sqlalchemy_utc.now import utcnow
from sqlalchemy_utc.sqltypes import UtcDateTime
from sqlalchemy_utils.types.uuid import UUIDType

from .mixin import PairMixin
from .order import OrderSide
from .orm import Base


class Trade(Base, PairMixin):
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    created_at = Column(
        UtcDateTime, nullable=False, index=True, default=utcnow(),
    )
    buy_order_id = Column(UUIDType, ForeignKey('order.id'), nullable=False)
    buy_order = relationship('Order', foreign_keys=[buy_order_id])
    sell_order_id = Column(UUIDType, ForeignKey('order.id'), nullable=False)
    sell_order = relationship('Order', foreign_keys=[sell_order_id])
    side = Column(EnumType(OrderSide, name='order_side'), nullable=False)
    volume = Column(Numeric(36, 18), nullable=False)
    price = Column(Numeric(36, 18), nullable=False)
    index = Column(Integer, nullable=False)

    __tablename__ = 'trade'
    __table_args__ = (
        CheckConstraint(volume > 0, name='ck_trade_volume'),
        CheckConstraint(price > 0, name='ck_trade_price'),
        CheckConstraint(index >= 0, name='ck_trade_index'),
        ForeignKeyConstraint(
            (buy_order_id, 'base_currency', 'quote_currency'),
            ('order.id', 'order.base_currency', 'order.quote_currency'),
        ),
        ForeignKeyConstraint(
            (sell_order_id, 'base_currency', 'quote_currency'),
            ('order.id', 'order.base_currency', 'order.quote_currency'),
        ),
        Index(
            'ix_trade_sort',
            'base_currency', 'quote_currency', 'created_at', 'index',
        ),
    )

    @hybrid_property
    def quote_volume(self):
        return self.price * self.volume
