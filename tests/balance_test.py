import decimal

from pytest import raises
from sqlalchemy.orm import Session
from typeguard import typechecked

from iu.balance import Balance


@typechecked
def test_balance_validate_amount(fx_balance: Balance):
    fx_balance.locked_amount = decimal.Decimal('1000')
    with raises(AssertionError):
        fx_balance.amount = decimal.Decimal('999')
    fx_balance.amount = decimal.Decimal('1000')


@typechecked
def test_balance_validate_locked_amount(fx_balance: Balance):
    fx_balance.locked_amount = decimal.Decimal('0')
    with raises(AssertionError):
        fx_balance.locked_amount = decimal.Decimal('-1')

    fx_balance.amount = decimal.Decimal('1000')
    with raises(AssertionError):
        fx_balance.locked_amount = decimal.Decimal('1001')
    fx_balance.locked_amount = decimal.Decimal('1000')


@typechecked
def test_balance_usable_amount(fx_balance: Balance, fx_session: Session):
    fx_balance.amount = decimal.Decimal('2000')
    fx_balance.locked_amount = decimal.Decimal('1000')
    assert fx_balance.usable_amount == decimal.Decimal('1000')
    fx_session.flush()

    assert fx_session.query(Balance.usable_amount).filter(
        Balance.user == fx_balance.user,
        Balance.currency == fx_balance.currency,
    ).scalar() == decimal.Decimal('1000')
