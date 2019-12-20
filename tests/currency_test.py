from pytest import raises
from sqlalchemy.exc import IntegrityError
from typeguard import typechecked

from iu.currency import Currency
from iu.orm import Session


@typechecked
def test_currency_check_constraints(
    fx_currency_usdt: Currency, fx_session: Session,
):
    fx_currency_usdt.decimals = -1
    with raises(IntegrityError) as e:
        fx_session.flush()
    assert 'violates check constraint "ck_currency_decimals' in str(e.value)


@typechecked
def test_currency_force_id_to_be_upper_case(fx_currency_usdt: Currency):
    fx_currency_usdt.id = 'usdt'
    assert fx_currency_usdt.id == 'USDT'
