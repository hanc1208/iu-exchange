from flask.blueprints import Blueprint
from flask.json import jsonify

from ..context import session
from ..currency import Currency

bp_currency = Blueprint('currency', __name__, url_prefix='/currencies')


@bp_currency.route('/')
def fetch_currencies():
    currencies = session.query(Currency).all()
    return jsonify(currencies)
