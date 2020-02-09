import uuid

from iu.order import Order, OrderSide
from iu.order_book import OrderBook


def test_order_book_insert(fx_wsgi_app):
    orders = [
        Order(id=uuid.UUID(int=0), price=1, side=OrderSide.sell),
        Order(id=uuid.UUID(int=1), price=3, side=OrderSide.sell),
        Order(id=uuid.UUID(int=2), price=5, side=OrderSide.sell),
        Order(id=uuid.UUID(int=3), price=7, side=OrderSide.sell),
        Order(id=uuid.UUID(int=4), price=9, side=OrderSide.sell),
        Order(id=uuid.UUID(int=5), price=1, side=OrderSide.sell),
        Order(id=uuid.UUID(int=6), price=2, side=OrderSide.sell),
        Order(id=uuid.UUID(int=7), price=9, side=OrderSide.sell),
        Order(id=uuid.UUID(int=8), price=10, side=OrderSide.sell),
        Order(id=uuid.UUID(int=9), price=5, side=OrderSide.sell),
    ]
    order_book = OrderBook(fx_wsgi_app)
    for order in orders:
        order_book.insert(order)
    expected = list(reversed([0, 5, 6, 1, 2, 9, 3, 4, 7, 8]))
    assert [o.id.int for o in order_book.sell_orders] == expected
    orders = [
        Order(id=uuid.UUID(int=0), price=9, side=OrderSide.buy),
        Order(id=uuid.UUID(int=1), price=7, side=OrderSide.buy),
        Order(id=uuid.UUID(int=2), price=5, side=OrderSide.buy),
        Order(id=uuid.UUID(int=3), price=3, side=OrderSide.buy),
        Order(id=uuid.UUID(int=4), price=1, side=OrderSide.buy),
        Order(id=uuid.UUID(int=5), price=9, side=OrderSide.buy),
        Order(id=uuid.UUID(int=6), price=8, side=OrderSide.buy),
        Order(id=uuid.UUID(int=7), price=1, side=OrderSide.buy),
        Order(id=uuid.UUID(int=8), price=0, side=OrderSide.buy),
        Order(id=uuid.UUID(int=9), price=5, side=OrderSide.buy),
    ]
    order_book = OrderBook(fx_wsgi_app)
    for order in orders:
        order_book.insert(order)
    expected = list(reversed([0, 5, 6, 1, 2, 9, 3, 4, 7, 8]))
    assert [o.id.int for o in order_book.buy_orders] == expected
