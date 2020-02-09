import argparse
import pathlib

from sqlalchemy.sql.functions import coalesce, sum as sqlsum
import toml

from iu.balance import Balance
from iu.context import session
from iu.order import Order
from iu.transaction import Transaction
from iu.web.wsgi import create_wsgi_app


parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument('-c', '--config', type=pathlib.Path)
args = parser.parse_args()

with open(args.config, 'r') as f:
    app = create_wsgi_app(toml.load(f))

app.test_request_context().__enter__()

session.query(Balance).update({
    Balance.amount: session.query(
        coalesce(sqlsum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == Balance.user_id,
        Transaction.currency == Balance.currency,
    ).as_scalar(),
    Balance.locked_amount: session.query(
        coalesce(sqlsum(Order.remaining_locked_amount), 0)
    ).filter(
        Order.user_id == Balance.user_id,
        Order.locking_currency == Balance.currency,
        Order.active,
    ).as_scalar()
}, synchronize_session='fetch')
session.commit()
