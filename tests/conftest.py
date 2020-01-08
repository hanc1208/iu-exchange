import datetime
import decimal
import itertools
import uuid
from typing import Any, Mapping, Sequence

from flask import Flask
from ormeasy.sqlalchemy import test_connection
from pytest import fixture
from typeguard import typechecked

from iu.balance import Balance
from iu.currency import Currency
from iu.market import Market
from iu.order import Order, OrderSide
from iu.orm import Base, Session, SessionType, create_session
from iu.user import User
from iu.web.wsgi import create_wsgi_app


@fixture
@typechecked
def fx_config() -> Mapping[str, Any]:
    return {
        'web': {
            'SECRET_KEY': 'de775515f6a4cdca5edfd71c2a32193d',
        },
        'database': {
            'url': 'postgresql:///iu-exchange-test',
        },
    }


@fixture
def fx_wsgi_app(fx_config: Mapping[str, Any]) -> Flask:
    wsgi_app = create_wsgi_app(fx_config)
    with wsgi_app.app_context():
        yield wsgi_app


@fixture
@typechecked
def fx_utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


@fixture
def fx_session(fx_wsgi_app: Flask) -> SessionType:
    session = create_session(fx_wsgi_app)
    engine = session.bind
    with test_connection(fx_wsgi_app, Base.metadata, engine) as connection:
        yield Session(bind=connection)


@fixture
@typechecked
def fx_user(fx_session: Session, fx_utcnow: datetime.datetime) -> User:
    user = User(
        id=uuid.UUID(int=1),
        created_at=fx_utcnow,
        email='user@iu.exchange',
        password='iu-exchange!',
    )
    fx_session.add(user)
    fx_session.flush()
    return user

@fixture
@typechecked
def fx_currencies(fx_session: Session) -> Mapping[str, Currency]:
    currencies = {
        'USDT': Currency(
            id='USDT',
            name='Tether',
            decimals=8,
            confirmations=12,
            minimum_deposit_amount=decimal.Decimal('2'),
            minimum_withdrawal_amount=decimal.Decimal('2'),
            withdrawal_fee=decimal.Decimal('1'),
            latest_synced_block_number=9345018,
        ),
        'BTC': Currency(
            id='BTC',
            name='Bitcoin',
            decimals=8,
            confirmations=1,
            minimum_deposit_amount=decimal.Decimal('0.001'),
            minimum_withdrawal_amount=decimal.Decimal('0.001'),
            withdrawal_fee=decimal.Decimal('0.0005'),
            latest_synced_block_number=614336,
        ),
    }
    fx_session.add_all(currencies.values())
    fx_session.flush()
    return currencies


@fixture
@typechecked
def fx_currency_usdt(fx_currencies: Mapping[str, Currency]) -> Currency:
    return fx_currencies['USDT']


@fixture
@typechecked
def fx_currency_btc(fx_currencies: Mapping[str, Currency]) -> Currency:
    return fx_currencies['BTC']


@fixture
@typechecked
def fx_market(
    fx_currencies: Mapping[str, Currency],
    fx_session: Session,
) -> Market:
    market = Market(
        pair='BTC/USDT',
        current_price=decimal.Decimal('8496.27'),
        maker_fee=decimal.Decimal('0.001'),
        taker_fee=decimal.Decimal('0.002'),
        minimum_order_amount=decimal.Decimal('0.0001'),
    )
    fx_session.add(market)
    fx_session.flush()
    return market


@fixture
@typechecked
def fx_user(fx_session: Session, fx_utcnow: datetime.datetime) -> User:
    user = User(
        id=uuid.UUID(int=1),
        created_at=fx_utcnow,
        email='user@iu.exchange',
        password='iu-exchange!',
    )
    fx_session.add(user)
    fx_session.flush()
    return user


@fixture
@typechecked
def fx_balance(
    fx_currency_usdt: Currency,
    fx_session: Session,
    fx_user: User,
) -> Balance:
    balance = Balance(
        user=fx_user,
        currency=fx_currency_usdt.id,
        amount=decimal.Decimal('100000'),
        locked_amount=decimal.Decimal('0'),
    )
    fx_session.add(balance)
    fx_session.flush()
    return balance


@fixture
@typechecked
def fx_orders(
    fx_market: Market,
    fx_session: Session,
    fx_user: User,
    fx_utcnow: datetime.datetime,
) -> Mapping[OrderSide, Sequence[Order]]:
    second = datetime.timedelta(seconds=1)
    order_map = {
        OrderSide.sell: [
            Order(
                id=uuid.UUID(int=1),
                created_at=fx_utcnow - 60 * second,
                volume=decimal.Decimal('20'),
                remaining_volume=decimal.Decimal('20'),
                price=decimal.Decimal('10000'),
            ),
            Order(
                id=uuid.UUID(int=2),
                created_at=fx_utcnow - 50 * second,
                volume=decimal.Decimal('25'),
                remaining_volume=decimal.Decimal('25'),
                price=decimal.Decimal('10000'),
            ),
            Order(
                id=uuid.UUID(int=3),
                created_at=fx_utcnow - 40 * second,
                volume=decimal.Decimal('30'),
                remaining_volume=decimal.Decimal('30'),
                price=decimal.Decimal('11000'),
            ),
        ],
        OrderSide.buy: [
            Order(
                id=uuid.UUID(int=4),
                created_at=fx_utcnow - 30 * second,
                volume=decimal.Decimal('15'),
                remaining_volume=decimal.Decimal('15'),
                price=decimal.Decimal('9000'),
            ),
            Order(
                id=uuid.UUID(int=5),
                created_at=fx_utcnow - 20 * second,
                volume=decimal.Decimal('10'),
                remaining_volume=decimal.Decimal('10'),
                price=decimal.Decimal('9000'),
            ),
            Order(
                id=uuid.UUID(int=6),
                created_at=fx_utcnow - 10 * second,
                volume=decimal.Decimal('5'),
                remaining_volume=decimal.Decimal('5'),
                price=decimal.Decimal('8000'),
            ),
        ],
    }
    for side, orders in order_map.items():
        for order in orders:
            order.side = side
            order.user = fx_user
            order.market = fx_market
    fx_session.add_all(itertools.chain.from_iterable(order_map.values()))
    fx_session.flush()
    return order_map


@fixture
@typechecked
def fx_buy_order(fx_orders: Mapping[OrderSide, Sequence[Order]]) -> Order:
    return fx_orders[OrderSide.buy][0]


@fixture
@typechecked
def fx_sell_order(fx_orders: Mapping[OrderSide, Sequence[Order]]) -> Order:
    return fx_orders[OrderSide.sell][0]
