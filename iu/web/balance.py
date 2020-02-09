from flask.blueprints import Blueprint
from flask.json import jsonify
from flask_login.utils import current_user, login_required

from ..context import session
from ..serializer import serialize

bp_balance = Blueprint('balance', __name__, url_prefix='/balances')


@bp_balance.route('/<currency>/deposit_address/', methods=['POST'])
@login_required
def create_deposit_address(currency: str):
    balance = current_user.balance_of(currency.upper(), lock=True)
    balance.create_deposit_address()
    session.commit()
    return jsonify(serialize(balance))
