import decimal
from typing import Any, Mapping
import uuid

from typeguard import typechecked

from ..order import Order, OrderSide


@typechecked
def parse_order(payload: Mapping[str, Any]) -> Order:
    return Order(
        id=uuid.UUID(payload['id']),
        user_id=payload['user_id'] and uuid.UUID(payload['user_id']),
        side=OrderSide(payload['side']),
        volume=decimal.Decimal(payload['volume']),
        remaining_volume=decimal.Decimal(payload['remaining_volume']),
        price=decimal.Decimal(payload['price']),
        base_currency=payload['base_currency'],
        quote_currency=payload['quote_currency'],
    )
