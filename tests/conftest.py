import datetime
import decimal
import uuid
from typing import Any, Mapping

from flask import Flask
from ormeasy.sqlalchemy import test_connection
from pytest import fixture
from typeguard import typechecked

from iu.currency import Currency
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
