from typing import Mapping

from sqlalchemy.orm import Session, aliased
from sqlalchemy.schema import Column
from sqlalchemy.types import Integer
from typeguard import typechecked

from iu.currency import Currency
from iu.mixin import PairMixin, PrimaryKeyPairMixin
from iu.orm import Base


class PairMixed(Base, PairMixin):
    __tablename__ = 'tests.mixin_test.pair_mixin'
    id = Column(Integer, primary_key=True)


class PrimaryKeyPairMixed(Base, PrimaryKeyPairMixin):
    __tablename__ = 'tests.mixin_test.primary_key_pair_mixin'


@typechecked
def test_pair_mixin(fx_currencies: Mapping[str, Currency], fx_session: Session):
    btc_usdt_pair = PairMixed(base_currency='BTC', quote_currency='USDT')
    assert btc_usdt_pair.pair == 'BTC/USDT'
    usdt_btc_pair = PairMixed()
    usdt_btc_pair.pair = 'USDT/BTC'
    assert usdt_btc_pair.base_currency == 'USDT'
    assert usdt_btc_pair.quote_currency == 'BTC'
    assert usdt_btc_pair.pair == 'USDT/BTC'

    fx_session.add(btc_usdt_pair)
    fx_session.add(usdt_btc_pair)
    fx_session.flush()

    assert fx_session.query(PairMixed.pair).filter(
        PairMixed.pair == 'BTC/USDT'
    ).scalar() == 'BTC/USDT'

    assert fx_session.query(PairMixed).filter(
        PairMixed.pair == 'BTC/USDT'
    ).one() == btc_usdt_pair

    other_pair_mixed = aliased(PairMixed)
    assert fx_session.query(PairMixed).outerjoin(
        other_pair_mixed, other_pair_mixed.pair == 'BTC/USDT'
    ).filter(
        PairMixed.pair == other_pair_mixed.pair
    ).one() == btc_usdt_pair


def test_primary_key_pair_mixed():
    pair_mixed = PrimaryKeyPairMixed(
        base_currency='BTC', quote_currency='USDT'
    )
    assert pair_mixed.pair == 'BTC/USDT'
