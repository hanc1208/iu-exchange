import decimal

from pytest import raises
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typeguard import typechecked

from iu.trade import Trade


@typechecked
def test_trade_check_constraints(fx_buy_trade: Trade, fx_session: Session):
    fx_session.begin_nested()
    fx_buy_trade.volume = decimal.Decimal('0')
    with raises(IntegrityError) as e:
        fx_session.flush()
    assert 'ck_trade_volume' in str(e.value)
    fx_session.rollback()

    fx_session.begin_nested()
    fx_buy_trade.price = decimal.Decimal('0')
    with raises(IntegrityError) as e:
        fx_session.flush()
    assert 'ck_trade_price' in str(e.value)
    fx_session.rollback()

    fx_session.begin_nested()
    fx_buy_trade.index = decimal.Decimal('-1')
    with raises(IntegrityError) as e:
        fx_session.flush()
    assert 'ck_trade_index' in str(e.value)
    fx_session.rollback()


@typechecked
def test_trade_quote_volume(fx_buy_trade: Trade):
    assert fx_buy_trade.quote_volume == decimal.Decimal('20000')
