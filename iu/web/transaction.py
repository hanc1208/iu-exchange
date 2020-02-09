from flask.globals import request
from flask.blueprints import Blueprint
from flask.json import jsonify
from flask_login.utils import current_user, login_required

from ..context import session
from ..currency import Currency
from ..serializer import serialize
from ..transaction import Deposit, Transaction, TransactionType

bp_transaction = Blueprint('transaction', __name__, url_prefix='/transactions')


@bp_transaction.route('/', methods=['GET'])
@login_required
def fetch_transactions():
    payload = request.values
    types = [TransactionType(type_) for type_ in payload.getlist('types[]')]
    currency = payload.get('currency')
    transactions = session.query(Transaction).filter(
        Transaction.user == current_user,
        Transaction.type.in_(types) if types else True,
        Transaction.currency == currency if currency else True,
    ).order_by(
        Transaction.created_at.desc(),
    ).limit(100).all()
    return jsonify(serialize(transactions))


@bp_transaction.route('/deposits/', methods=['GET'])
@login_required
def fetch_deposits():
    payload = request.values
    currency_id = payload.get('currency')
    currency = currency_id and session.query(Currency).get(currency_id)
    deposits = session.query(Deposit).filter(
        Deposit.user == current_user,
        Deposit.currency == currency_id if currency_id else True,
        ~Deposit.confirmed,
    ).order_by(
        Deposit.block_number.desc(),
        Deposit.amount.desc(),
    ).limit(100).all()
    return jsonify([
        {
            **serialize(deposit),
            'confirmations': (
                currency.latest_synced_block_number - deposit.block_number + 1
            ),
        }
        for deposit in deposits
        if currency.latest_synced_block_number >= deposit.block_number
    ])
