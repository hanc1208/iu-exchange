import decimal
import uuid

from flask.blueprints import Blueprint
from flask.globals import request, session as flask_session
from flask.json import jsonify
from flask_login.utils import current_user, login_required
from werkzeug.exceptions import Unauthorized

from ..context import session
from ..order import Order, OrderSide

bp_order = Blueprint('order', __name__, url_prefix='/orders')


@bp_order.route('/', methods=['POST'])
def place_order():
    if 'user_id' not in flask_session:
        raise Unauthorized()
    data = request.get_json()

    volume = decimal.Decimal(data['volume'])
    price = decimal.Decimal(data['price'])
    _, quote_currency = data['pair'].split('/')
    if quote_currency == 'ETH':
        price_quotations = [
            [0, '0.000001'],
        ]
    else:
        price_quotations = [
            [2000000, 1000],
            [1000000, 500],
            [500000, 100],
            [100000, 50],
            [10000, 10],
            [1000, 5],
            [100, 1],
            [10, '0.1'],
            [0, '0.01'],
        ]
    for threshold, priceQuotation in price_quotations:
        if price >= decimal.Decimal(threshold):
            price = (
                price - price % decimal.Decimal(priceQuotation)
            )
            break
    if quote_currency == 'ETH':
        price = min(decimal.Decimal('1'), price)
        price = max(decimal.Decimal('0.000001'), price)
    else:
        price = min(decimal.Decimal('100000000'), price)
        price = min(decimal.Decimal('0.01'), price)
    order = Order(
        id=uuid.uuid4(),
        user_id=flask_session['user_id'],
        side=OrderSide(data['side']),
        volume=volume,
        remaining_volume=volume,
        price=price,
        pair=data['pair'],
    )
    from ..order_book.mq import enqueue_place_order
    from flask import current_app
    enqueue_place_order(current_app, order)
    return jsonify()


@bp_order.route('/', methods=['DELETE'])
@login_required
def delete_orders():
    payload = request.get_json()
    pair = payload['pair']
    from ..order_book.mq import enqueue_delete_order
    orders = session.query(Order).filter(
        Order.active,
        Order.user == current_user,
        Order.pair == pair,
    )
    from flask import current_app
    enqueue_delete_order(current_app, orders)
    return jsonify()
