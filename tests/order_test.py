import operator

from sqlalchemy.sql.expression import asc, desc

from iu.order import OrderSide


def test_order_side():
    assert OrderSide.buy.order_op is desc
    assert OrderSide.sell.order_op is asc

    assert OrderSide.buy.compare_op is operator.ge
    assert OrderSide.sell.compare_op is operator.le

    assert ~OrderSide.buy is OrderSide.sell
    assert ~OrderSide.sell is OrderSide.buy

    assert OrderSide.buy.choice(buy=1, sell=2) == 1
    assert OrderSide.sell.choice(buy=1, sell=2) == 2
