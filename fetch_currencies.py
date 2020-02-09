import concurrent.futures.thread
import decimal
import pathlib
import shutil
import sys

from requests import get
import toml

from iu.context import session
from iu.currency import Currency
from iu.market import Market
from iu.web.wsgi import create_wsgi_app

with open(sys.argv[1], 'r') as f:
    app = create_wsgi_app(toml.load(f))

app.test_request_context().__enter__()

currencies = []
markets = []
tickers = get('https://api.coinmarketcap.com/v1/ticker/').json()


def fetch_icon(args):
    id_, symbol = args
    url = f'https://github.com/giekaton/cryptocurrency-logos/raw/master/coins/64x64/{id_}.png'
    if id_ == 'bitcoin-sv':
        url = 'https://s2.coinmarketcap.com/static/img/coins/16x16/3602.png'
    print(id_, symbol)
    icon = get(url, stream=True).raw
    icon.decode_content = True
    with open(pathlib.Path('iu') / 'web' / 'static' / 'currencies' / f'{symbol}.png', 'wb') as f:
        shutil.copyfileobj(icon, f)


existing_currencies = [id_ for id_, in session.query(Currency.id)]
icon_args = []

currency = Currency(
    id='KRW',
    name='Korea Won',
    decimals=0,
    confirmations=1,
    latest_synced_block_number=0,
    minimum_deposit_amount=1000,
    minimum_withdrawal_amount=2000,
    withdrawal_fee=1000,
)
currencies.append(currency)
for ticker in tickers[:10]:
    id_ = ticker['id']
    symbol = ticker['symbol']
    if symbol not in ('BTC', 'ETH', 'USDT', 'XRP'):
        continue
    currency = Currency(
        id=symbol,
        name=ticker['name'],
        decimals=8,
        confirmations={
            'BTC': 1,
            'ETH': 12,
        }.get(symbol, 1),
        minimum_deposit_amount={
            'BTC': decimal.Decimal('0.001'),
            'ETH': decimal.Decimal('0.02'),
        }.get(symbol, 0),
        minimum_withdrawal_amount={
            'BTC': decimal.Decimal('0.001'),
            'ETH': decimal.Decimal('0.02'),
        }.get(symbol, 0),
        withdrawal_fee={
            'BTC': decimal.Decimal('0.0005'),
            'ETH': decimal.Decimal('0.01'),
        }.get(symbol, 0),
        latest_synced_block_number=0,
    )
    currencies.append(currency)
    maker_fee = decimal.Decimal('0.001')
    taker_fee = decimal.Decimal('0.001')
    markets.append(
        Market(
            base_currency=symbol,
            quote_currency='KRW',
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            minimum_order_amount=decimal.Decimal(1000),
        )
    )
    if symbol != 'BTC':
        markets.append(
            Market(
                base_currency=symbol,
                quote_currency='BTC',
                maker_fee=maker_fee,
                taker_fee=taker_fee,
                minimum_order_amount=decimal.Decimal(0.0005),
            )
        )
    if symbol != 'USDT':
        markets.append(
            Market(
                base_currency=symbol,
                quote_currency='USDT',
                maker_fee=maker_fee,
                taker_fee=taker_fee,
                minimum_order_amount=decimal.Decimal(1),
            )
        )
    icon_args.append((id_, symbol))

with concurrent.futures.thread.ThreadPoolExecutor(16) as executor:
    list(executor.map(fetch_icon, icon_args))

session.add_all(currencies)
session.flush()
session.add_all(markets)
session.commit()
