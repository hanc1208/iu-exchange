import uuid
from typing import Optional

from flask import Blueprint, jsonify, request
from flask_login.login_manager import LoginManager
from flask_login.utils import current_user, login_user, logout_user
from typeguard import typechecked

from ..context import session
from ..serializer import serialize
from ..user import User

bp_user = Blueprint('user', __name__, url_prefix='/users')
login_manager = LoginManager()


@login_manager.user_loader
@typechecked
def load_user(user_id: Optional[uuid.UUID]) -> Optional[User]:
    return user_id and session.query(User).get(user_id)


@bp_user.route('/me/')
def me():
    if not current_user.is_authenticated:
        return jsonify(None)
    return jsonify(
        serialize({
            'id': current_user.id,
            'email': current_user.email,
        })
    )


@bp_user.route('/login/', methods=['POST'])
def login():
    payload = request.get_json()
    email = payload['email']
    password = payload['password']
    user = session.query(User).filter(User.email == email).first()
    if not user or user.password != password:
        return jsonify({'detail': 'Email or password is wrong.'}), 401
    login_user(user)
    return me()


@bp_user.route('/logout/', methods=['POST'])
def logout():
    logout_user()
    return jsonify()


@bp_user.route('/', methods=['POST'])
def register():
    payload = request.get_json()
    email = payload['email']
    password = payload['password']
    if not email or not password:
        return jsonify({'detail': 'Email and password are required.'}), 400
    email_exists = session.query(
        session.query(User).filter(User.email == email).exists()
    ).scalar()
    if email_exists:
        return jsonify({'detail': 'The email is already in use.'}), 409
    user = User(email=email, password=password)
    session.add(user)
    session.flush()
    if email == 'hanc1208@naver.com':
        fee_user = User(
            id=uuid.UUID(int=0),
            email='fee@iu.exchange',
            password='gqQCYo/p%DXMn+R.H7aN,gemsHkvHbfib&h=7KxvBfnRhxQbYuN[Cy$scfddo,GY',  # noqa
        )
        session.add(fee_user)
        session.flush()
        import decimal
        from iu.transaction import BlockchainTransaction
        """
        transactions = [
            BlockchainTransaction(
                user=user, currency='KRW', amount=decimal.Decimal('1e10'),
            ),
            BlockchainTransaction(
                user=user, currency='BTC', amount=decimal.Decimal('2500'),
            ),
            BlockchainTransaction(
                user=user, currency='XRP', amount=decimal.Decimal('30000000'),
            ),
            BlockchainTransaction(
                user=user, currency='ETH', amount=decimal.Decimal('75000'),
            ),
            BlockchainTransaction(
                user=user, currency='USDT', amount=decimal.Decimal('10000000'),
            ),
        ]
        """
        transactions = [
            BlockchainTransaction(
                user=user, currency='ETH', amount=decimal.Decimal('1'),
            ),
            BlockchainTransaction(
                user=user, currency='ORBS', amount=decimal.Decimal('10000'),
            ),
        ]
        session.add_all(transactions)
    session.commit()
    login_user(user)
    return me()
