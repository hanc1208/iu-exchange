import datetime
import decimal
import enum
import functools
from typing import Any, Mapping, Union
import uuid

from sqlalchemy.inspection import inspect
from typeguard import typechecked

from .market import Market
from .trade import Trade
from .orm import Base


@functools.singledispatch
def serialize(obj):
    raise NotImplementedError


@serialize.register(type(None))
@typechecked
def serialize_none(obj: None) -> None:
    return obj


@serialize.register(bool)
@typechecked
def serialize_bool(obj: bool) -> bool:
    return obj


@serialize.register(int)
@typechecked
def serialize_int(obj: int) -> int:
    return obj


@serialize.register(float)
@typechecked
def serialize_float(obj: float) -> float:
    return obj


@serialize.register(str)
@typechecked
def serialize_str(obj: str) -> str:
    return obj


@serialize.register(list)
@typechecked
def serialize_list(obj: list) -> list:
    return [serialize(o) for o in obj]


@serialize.register(set)
@typechecked
def serialize_set(obj: set) -> set:
    return {serialize(o) for o in obj}


@serialize.register(dict)
@typechecked
def serialize_dict(
    obj: Mapping[Union[int, str], Any]
) -> Mapping[str, Any]:
    return {str(k): serialize(v) for k, v in obj.items()}


@serialize.register(enum.Enum)
@typechecked
def serialize_enum(obj: enum.Enum) -> Any:
    return serialize(obj.value)


@serialize.register(datetime.date)
@typechecked
def serialize_date(obj: datetime.date) -> str:
    return obj.isoformat()


@serialize.register(decimal.Decimal)
@typechecked
def serialize_decimal(obj: decimal.Decimal) -> str:
    return str(
        obj.quantize(decimal.Decimal(1)) if obj == obj.to_integral()
        else obj.normalize()
    )


@serialize.register(uuid.UUID)
@typechecked
def serialize_uuid(obj: uuid.UUID) -> str:
    return str(obj)


@serialize.register(Base)
@typechecked
def serialize_db_model(obj: Base) -> Mapping[str, Any]:
    return serialize({
        attr.key: getattr(obj, attr.key)
        for attr in inspect(obj).mapper.column_attrs
    })


@serialize.register(Market)
@typechecked
def serialize_market(obj: Market) -> Mapping[str, Any]:
    return serialize({
        'pair': obj.pair,
        'currentPrice': obj.current_price,
        'makerFee': obj.maker_fee,
        'takerFee': obj.taker_fee,
        'minimumOrderAmount': obj.minimum_order_amount,
    })


@serialize.register(Trade)
@typechecked
def serialize_trade(obj: Trade) -> Mapping[str, Any]:
    return serialize({
        'id': obj.id,
        'createdAt': obj.created_at,
        'pair': obj.pair,
        'side': obj.side,
        'price': obj.price,
        'volume': obj.volume,
    })
