import argparse
import pathlib

from sqlalchemy.sql.functions import coalesce, sum as sqlsum
import toml

from iu.balance import Balance
from iu.context import session
from iu.order import Order
from iu.serializer import serialize
from iu.transaction import Transaction, TransactionType
from iu.web.wsgi import create_wsgi_app

parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument('-c', '--config', type=pathlib.Path)
args = parser.parse_args()

with open(args.config, 'r') as f:
    app = create_wsgi_app(toml.load(f))

app.test_request_context().__enter__()

transaction_query = session.query(sqlsum(Transaction.amount)).filter(
    Transaction.user_id == Balance.user_id,
    Transaction.currency == Balance.currency
)
order_query = session.query(
    coalesce(sqlsum(Order.remaining_locked_amount), 0),
).filter(
    Order.user_id == Balance.user_id,
    Order.locking_currency == Balance.currency,
    Order.active,
)
query = session.query(
    Balance, transaction_query.as_scalar(), order_query.as_scalar(),
).group_by(
    Balance.user_id, Balance.currency
).filter(
    (Balance.amount != transaction_query) |
    (Balance.locked_amount != order_query)
)
for balance, transaction, order in query:
    print(serialize(balance), transaction, order)

query = session.query(Transaction.currency, sqlsum(Transaction.amount)).filter(
    Transaction.type != TransactionType.blockchain
).group_by(
    Transaction.currency
).having(
    sqlsum(Transaction.amount) != 0
)
for currency, transaction in query:
    print(currency, transaction)

transaction_query = session.query(sqlsum(Transaction.amount)).filter(
    Transaction.type == TransactionType.blockchain,
    Transaction.currency == Balance.currency
)
query = session.query(
    Balance.currency, sqlsum(Balance.amount), transaction_query.as_scalar(),
).group_by(
    Balance.currency
).having(
    sqlsum(Balance.amount) != transaction_query
)
for currency, balance, transaction in query:
    print(currency, balance, transaction)
