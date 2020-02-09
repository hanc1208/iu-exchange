from __future__ import annotations

import datetime
import decimal
import enum
from typing import List, Optional, Dict, Tuple

from sqlalchemy.schema import CheckConstraint, Column
from sqlalchemy.sql.expression import extract, cast
from sqlalchemy.sql.functions import func
from sqlalchemy.types import Integer, Numeric
from sqlalchemy_enum34 import EnumType
from sqlalchemy_utc.sqltypes import UtcDateTime
from typeguard import typechecked

from .mixin import PrimaryKeyPairMixin
from .trade import Trade
from .orm import Base, SessionType


class CandleUnitType(enum.Enum):
    minutes = 'minutes'
    tick = 'tick'


CandleUnitKey = Tuple[int, CandleUnitType]


class Candle(Base, PrimaryKeyPairMixin):
    available_units: Tuple[CandleUnitKey] = (
        (1, CandleUnitType.minutes),
        (3, CandleUnitType.minutes),
        (5, CandleUnitType.minutes),
        (15, CandleUnitType.minutes),
        (30, CandleUnitType.minutes),
        (60, CandleUnitType.minutes),
        (240, CandleUnitType.minutes),
        (1440, CandleUnitType.minutes),
        (4320, CandleUnitType.minutes),
        (10080, CandleUnitType.minutes),
    )

    unit = Column(Integer, primary_key=True)
    unit_type = Column(
        EnumType(CandleUnitType, name='candle_unit_type'), primary_key=True,
    )
    timestamp = Column(UtcDateTime, nullable=False, primary_key=True)
    updated_at = Column(UtcDateTime, nullable=False)
    open = Column(Numeric(36, 18), nullable=False)
    high = Column(Numeric(36, 18), nullable=False)
    low = Column(Numeric(36, 18), nullable=False)
    close = Column(Numeric(36, 18), nullable=False)
    volume = Column(Numeric(36, 18), nullable=False)
    quote_volume = Column(Numeric(36, 18), nullable=False)

    __tablename__ = 'candle'

    __table_args__ = (
        CheckConstraint(
            (
                (open > 0) &
                (high > 0) &
                (low > 0) &
                (close > 0) &
                (volume > 0) &
                (quote_volume > 0)
            ),
            'ck_candle_positive',
        ),
    )

    @property
    def next_timestamp(self):
        assert self.unit_type is CandleUnitType.minutes
        return self.timestamp + datetime.timedelta(minutes=self.unit)

    @property
    @typechecked
    def unit_key(self) -> CandleUnitKey:
        return self.unit, self.unit_type

    @unit_key.setter
    @typechecked
    def unit_key(self, value: CandleUnitKey) -> None:
        unit, unit_type = value
        self.unit = unit
        self.unit_type = unit_type

    @property
    @typechecked
    def price(self) -> decimal.Decimal:
        return self.close

    @price.setter
    @typechecked
    def price(self, value: decimal.Decimal) -> None:
        self.open = self.open or value
        self.high = max(self.high, value) if self.high else value
        self.low = min(self.low, value) if self.low else value
        self.close = value

    @typechecked
    def update(
        self,
        price: decimal.Decimal,
        volume: decimal.Decimal,
        updated_at: datetime.datetime,
    ) -> None:
        self.price = price
        self.volume += volume
        self.quote_volume += price * volume
        assert updated_at >= self.updated_at
        self.updated_at = updated_at

    @typechecked
    def merge(self, other: Candle) -> None:
        self.high = max(self.high, other.high)
        self.low = min(self.low, other.low)
        self.close = other.close
        self.volume += other.volume
        self.quote_volume += other.quote_volume
        assert other.updated_at >= self.updated_at
        self.updated_at = other.updated_at

    @staticmethod
    @typechecked
    def fetch_last_candles(
        *, session: SessionType, pair: str,
    ) -> Dict[CandleUnitKey, Optional[Candle]]:
        return {
            (unit, unit_type): session.query(Candle).filter(
                Candle.pair == pair,
                Candle.unit == unit,
                Candle.unit_type == unit_type,
            ).order_by(
                Candle.timestamp.desc(),
            ).limit(1).first()
            for unit, unit_type in Candle.available_units
        }

    @staticmethod
    @typechecked
    def get_timestamp_of(
        dt: datetime.datetime,
        *,
        unit_key: CandleUnitKey,
    ) -> datetime.datetime:
        unit, unit_type = unit_key
        assert unit_type is CandleUnitType.minutes
        timestamp = dt.timestamp()
        return datetime.datetime.utcfromtimestamp(
            timestamp - timestamp % (unit * 60)
        ).replace(
            tzinfo=datetime.timezone.utc,
        )

    @staticmethod
    @typechecked
    def update_lack_candles(
        *,
        session: SessionType,
        pair: str,
    ) -> Dict[CandleUnitKey, Optional[Candle]]:
        base_currency, quote_currency = pair.split('/')
        last_candles = Candle.fetch_last_candles(session=session, pair=pair)
        last_trades = {
            unit_key: session.query(Trade.created_at).filter(
                Trade.pair == pair,
            ).order_by(
                Trade.created_at.desc(),
            ).limit(1).scalar()
            for unit_key in Candle.available_units
        }
        for unit_key in Candle.available_units:
            last_traded_at = last_trades[unit_key]
            if not last_traded_at:
                continue
            candles = []
            candle = last_candles[unit_key]
            if candle:
                candles.append(candle)
            if not candle or last_traded_at > candle.updated_at:
                Candle.interpolate(
                    session=session,
                    candles=candles,
                    pair=pair,
                    unit_key=unit_key,
                )
                if candles:
                    session.add_all(candles)
                    last_candles[unit_key] = candles[0]
        return last_candles

    @staticmethod
    @typechecked
    def interpolate(
        session: SessionType,
        candles: List[Candle],
        pair: str,
        unit_key: CandleUnitKey,
    ):
        uncached_candles = sorted(
            Candle.query(
                session=session,
                pair=pair,
                unit_key=unit_key,
                created_at=(
                    candles[0].updated_at + datetime.timedelta(microseconds=1)
                    if candles else None
                ),
            ),
            key=lambda c: c.timestamp,
            reverse=True,
        )
        if not uncached_candles:
            return
        uncached_candle = uncached_candles[-1]
        if not candles or uncached_candle.timestamp > candles[0].timestamp:
            candles.extend(uncached_candles)
            candles.sort(key=lambda c: c.timestamp, reverse=True)
        else:
            assert candles[0].timestamp == uncached_candle.timestamp, \
                (candles[0].timestamp, uncached_candle.timestamp)
            candles[0].merge(uncached_candle)
            candles.extend(uncached_candles[:-1])
            candles.sort(key=lambda c: c.timestamp, reverse=True)

    @staticmethod
    @typechecked
    def query(
        session: SessionType,
        pair: str,
        unit_key: CandleUnitKey,
        created_at: Optional[datetime.datetime]=None,
        max_created_at: Optional[datetime.datetime]=None,
    ) -> List[Candle]:
        unit, unit_type = unit_key
        assert unit_type is CandleUnitType.minutes
        timestamp = func.date_trunc(
            'minute',
            Trade.created_at -
            datetime.timedelta(seconds=1) *
            (
                cast(func.floor(extract('epoch', Trade.created_at)), Integer) %
                (unit * 60)
            )
        ).label('timestamp')
        over = dict(
            partition_by=timestamp,
            order_by=(Trade.created_at, Trade.index),
            range_=(None, None),
        )
        query = session.query(
            timestamp,
            func.max(Trade.created_at).over(**over).label('updated_at'),
            func.first_value(Trade.price).over(**over).label('open'),
            func.last_value(Trade.price).over(**over).label('close'),
            func.min(Trade.price).over(**over).label('low'),
            func.max(Trade.price).over(**over).label('high'),
            func.sum(Trade.volume).over(**over).label('volume'),
            func.sum(Trade.quote_volume).over(**over).label('quote_volume'),
        ).filter(
            Trade.pair == pair,
            Trade.created_at >= created_at if created_at else True,
            Trade.created_at < max_created_at if max_created_at else True,
        ).distinct(
            timestamp,
        )
        return [
            Candle(
                pair=pair,
                unit_key=unit_key,
                timestamp=candle.timestamp,
                updated_at=candle.updated_at,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                quote_volume=candle.quote_volume,
            )
            for candle in query
        ]

    @staticmethod
    @typechecked
    def get_daily_candle(
        session: SessionType,
        pair: str,
    ) -> Optional[Candle]:
        over = dict(order_by=Candle.timestamp, range_=(None, None))
        now = datetime.datetime.now(datetime.timezone.utc)
        yesterday = now - datetime.timedelta(days=1)
        unit_key = (1, CandleUnitType.minutes)
        intermediate_candle = session.query(
            func.min(Candle.timestamp).over(**over).label('timestamp'),
            func.max(Candle.updated_at).over(**over).label('updated_at'),
            func.first_value(Candle.open).over(**over).label('open'),
            func.last_value(Candle.close).over(**over).label('close'),
            func.min(Candle.low).over(**over).label('low'),
            func.max(Candle.high).over(**over).label('high'),
            func.sum(Candle.volume).over(**over).label('volume'),
            func.sum(Candle.quote_volume).over(**over).label('quote_volume'),
        ).filter(
            Candle.pair == pair,
            Candle.timestamp >
            Candle.get_timestamp_of(yesterday, unit_key=unit_key),
            Candle.timestamp <
            Candle.get_timestamp_of(now, unit_key=unit_key),
            Candle.unit == 1,
            Candle.unit_type == CandleUnitType.minutes,
        ).distinct().first()
        if intermediate_candle:
            intermediate_candle = Candle(
                pair=pair,
                unit_key=(1440, CandleUnitType.minutes),
                timestamp=intermediate_candle.timestamp,
                updated_at=intermediate_candle.updated_at,
                open=intermediate_candle.open,
                high=intermediate_candle.high,
                low=intermediate_candle.low,
                close=intermediate_candle.close,
                volume=intermediate_candle.volume,
                quote_volume=intermediate_candle.quote_volume,
            )
        yesterday_candles = Candle.query(
            session=session,
            pair=pair,
            unit_key=unit_key,
            created_at=Candle.get_timestamp_of(yesterday, unit_key=unit_key),
            max_created_at=(
                Candle.get_timestamp_of(yesterday, unit_key=unit_key) +
                datetime.timedelta(minutes=1)
            ),
        )
        assert len(yesterday_candles) <= 1
        yesterday_candle = yesterday_candles and yesterday_candles[0]
        today_candles = Candle.query(
            session=session,
            pair=pair,
            unit_key=unit_key,
            created_at=Candle.get_timestamp_of(now, unit_key=unit_key),
            max_created_at=now,
        )
        assert len(today_candles) <= 1
        today_candle = today_candles and today_candles[0]
        candles = [
            c for c in [yesterday_candle, intermediate_candle, today_candle]
            if c
        ]
        if not candles:
            return
        candle = candles.pop()
        while candles:
            _candle = candles.pop()
            _candle.merge(candle)
            candle = _candle
        return candle
