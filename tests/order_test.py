import datetime
import decimal
import operator

from pytest import raises
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import asc, desc
from typeguard import typechecked

from iu.order import Order, OrderSide


def test_order_side():
    assert OrderSide.buy.order_op is desc
    assert OrderSide.sell.order_op is asc

    assert OrderSide.buy.compare_op is operator.ge
    assert OrderSide.sell.compare_op is operator.le

    assert ~OrderSide.buy is OrderSide.sell
    assert ~OrderSide.sell is OrderSide.buy

    assert OrderSide.buy.choice(buy=1, sell=2) == 1
    assert OrderSide.sell.choice(buy=1, sell=2) == 2


@typechecked
def test_order_check_constraints(
    fx_buy_order: Order,
    fx_session: Session,
    fx_utcnow: datetime.datetime,
):
    fx_session.begin_nested()
    fx_buy_order.price = decimal.Decimal('0')
    with raises(IntegrityError) as e:
        fx_session.flush()
    assert 'ck_order_price_positive' in str(e.value)
    fx_session.rollback()

    fx_session.begin_nested()
    fx_buy_order.volume = decimal.Decimal('0')
    with raises(IntegrityError) as e:
        fx_session.flush()
    assert 'ck_order_volume' in str(e.value)
    fx_session.rollback()

    fx_session.begin_nested()
    fx_buy_order.remaining_volume = decimal.Decimal('-1')
    with raises(IntegrityError) as e:
        fx_session.flush()
    assert 'violates check constraint' in str(e.value)
    fx_session.rollback()

    fx_session.begin_nested()
    fx_buy_order.volume = decimal.Decimal('100')
    fx_buy_order.remaining_volume = decimal.Decimal('101')
    with raises(IntegrityError) as e:
        fx_session.flush()
    assert 'ck_order_volume' in str(e.value)
    fx_session.rollback()

    fx_session.begin_nested()
    fx_buy_order.pair = 'BTC/BTC'
    with raises(IntegrityError) as e:
        fx_session.flush()
    assert 'ck_order_currency' in str(e.value)
    fx_session.rollback()

    fx_session.begin_nested()
    fx_buy_order.remaining_volume = decimal.Decimal('0')
    fx_buy_order.filled_at = None
    with raises(IntegrityError) as e:
        fx_session.flush()
    assert 'ck_order_filled' in str(e.value)
    fx_session.rollback()

    fx_session.begin_nested()
    fx_buy_order.remaining_volume = decimal.Decimal('1')
    fx_buy_order.filled_at = fx_utcnow
    with raises(IntegrityError) as e:
        fx_session.flush()
    assert 'ck_order_filled' in str(e.value)
    fx_session.rollback()

    fx_session.begin_nested()
    fx_buy_order.remaining_volume = decimal.Decimal('0')
    fx_buy_order.cancel()
    with raises(IntegrityError) as e:
        fx_session.flush()
    assert 'ck_order_canceled' in str(e.value)
    fx_session.rollback()


@typechecked
def test_order_repr(fx_buy_order: Order):
    assert repr(fx_buy_order) == 'side=buy price=9000 volume=15'


@typechecked
def test_order_validate_remaining_volume(fx_buy_order: Order):
    assert not fx_buy_order.filled
    fx_buy_order.remaining_volume = decimal.Decimal('0')
    assert fx_buy_order.filled


@typechecked
def test_order_locking_currency(
    fx_buy_order: Order,
    fx_sell_order: Order,
    fx_session: Session,
):
    assert fx_buy_order.locking_currency == 'USDT'
    assert fx_sell_order.locking_currency == 'BTC'

    assert fx_session.query(Order.locking_currency).filter(
        Order.id == fx_buy_order.id,
    ).scalar() == 'USDT'
    assert fx_session.query(Order.locking_currency).filter(
        Order.id == fx_sell_order.id,
    ).scalar() == 'BTC'


@typechecked
def test_order_filled_volume(fx_buy_order: Order, fx_session: Session):
    fx_buy_order.volume = decimal.Decimal('2000')
    fx_buy_order.remaining_volume = decimal.Decimal('1000')

    assert fx_buy_order.filled_volume == decimal.Decimal('1000')
    assert fx_session.query(Order.filled_volume).filter(
        Order.id == fx_buy_order.id,
    ).scalar() == decimal.Decimal('1000')


@typechecked
def test_order_locked_volume(
    fx_buy_order: Order,
    fx_sell_order: Order,
    fx_session: Session,
):
    assert fx_buy_order.locked_amount == decimal.Decimal('135000')
    assert fx_sell_order.locked_amount == decimal.Decimal('20')

    assert fx_session.query(Order.locked_amount).filter(
        Order.id == fx_buy_order.id,
    ).scalar() == decimal.Decimal('135000')
    assert fx_session.query(Order.locked_amount).filter(
        Order.id == fx_sell_order.id,
    ).scalar() == decimal.Decimal('20')


@typechecked
def test_order_remaining_locked_amount(
    fx_buy_order: Order,
    fx_sell_order: Order,
    fx_session: Session,
):
    fx_buy_order.volume = decimal.Decimal('200')
    fx_buy_order.remaining_volume = decimal.Decimal('100')
    fx_sell_order.volume = decimal.Decimal('300')
    fx_sell_order.remaining_volume = decimal.Decimal('150')

    assert fx_buy_order.remaining_locked_amount == decimal.Decimal('900000')
    assert fx_sell_order.remaining_locked_amount == decimal.Decimal('150')

    assert fx_session.query(Order.remaining_locked_amount).filter(
        Order.id == fx_buy_order.id,
    ).scalar() == decimal.Decimal('900000')
    assert fx_session.query(Order.remaining_locked_amount).filter(
        Order.id == fx_sell_order.id,
    ).scalar() == decimal.Decimal('150')


@typechecked
def test_order_filled(fx_buy_order: Order, fx_session: Session):
    assert fx_buy_order.filled_at is None
    assert not fx_buy_order.filled
    assert fx_session.query(Order.filled).filter(
        Order.id == fx_buy_order.id,
    ).scalar() is False

    fx_buy_order.remaining_volume = decimal.Decimal('0')
    fx_session.flush()
    assert isinstance(fx_buy_order.filled_at, datetime.datetime)
    assert fx_buy_order.filled
    assert fx_session.query(Order.filled).filter(
        Order.id == fx_buy_order.id,
    ).scalar() is True


@typechecked
def test_order_canceled(fx_buy_order: Order, fx_session: Session):
    assert fx_buy_order.canceled_at is None
    assert not fx_buy_order.canceled
    assert fx_session.query(Order.canceled).filter(
        Order.id == fx_buy_order.id,
    ).scalar() is False

    fx_buy_order.cancel()
    fx_session.flush()
    assert isinstance(fx_buy_order.canceled_at, datetime.datetime)
    assert fx_buy_order.canceled
    assert fx_session.query(Order.canceled).filter(
        Order.id == fx_buy_order.id,
    ).scalar() is True


@typechecked
def test_order_active(fx_buy_order: Order, fx_session: Session):
    assert not fx_buy_order.filled
    assert not fx_buy_order.canceled
    assert fx_buy_order.active
    assert fx_session.query(Order.active).filter(
        Order.id == fx_buy_order.id,
    ).scalar() is True

    fx_buy_order.remaining_volume = decimal.Decimal('0')
    fx_session.flush()
    assert not fx_buy_order.active
    assert fx_session.query(Order.active).filter(
        Order.id == fx_buy_order.id,
    ).scalar() is False

    fx_buy_order.filled_at = None
    fx_buy_order.remaining_volume = decimal.Decimal('1')
    fx_buy_order.cancel()
    fx_session.flush()
    assert not fx_buy_order.active
    assert fx_session.query(Order.active).filter(
        Order.id == fx_buy_order.id,
    ).scalar() is False
