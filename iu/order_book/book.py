import asyncio
import concurrent.futures.thread
import contextlib
import datetime
import decimal
import itertools
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Set, Tuple

from flask.app import Flask
from pika.adapters.blocking_connection import (
    BlockingChannel, BlockingConnection,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import FlushError
from sqlalchemy.sql.expression import tuple_
from sqlalchemy_utc.now import utcnow
from typeguard import typechecked
from websockets import connect

from ..balance import Balance
from ..candle import Candle, CandleUnitKey
from ..exc import NotEnoughBalance
from ..market import Market
from ..order import Order, OrderSide
from ..orm import SessionType, create_session
from ..serializer import serialize
from ..trade import Trade
from ..transaction import TradeTransaction, Transaction, TransactionType
from .mq import get_mq_channel, get_mq_connection, get_mq_queue_name
from .util import parse_order


logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


@dataclass
class OrderBook:
    app: Flask
    session: SessionType = None
    market: Market = None
    mq_channel: BlockingChannel = None
    mq_connection: BlockingConnection = None
    executor: concurrent.futures.thread.ThreadPoolExecutor = None
    # FIXME: Use builtin priority queue
    sell_orders: List[Order] = field(default_factory=list)
    buy_orders: List[Order] = field(default_factory=list)
    merged_sell_orders: Dict[decimal.Decimal, decimal.Decimal] = field(
        default_factory=dict
    )
    merged_buy_orders: Dict[decimal.Decimal, decimal.Decimal] = field(
        default_factory=dict
    )
    order_ids: Set[uuid.UUID] = field(default_factory=set)
    candles: Dict[CandleUnitKey, Candle] = None

    @property
    def pair(self):
        return self.market.pair

    @typechecked
    def remove(self, side: OrderSide, order_id: uuid.UUID):
        orders = side.choice(buy=self.buy_orders, sell=self.sell_orders)
        for i in range(len(orders) - 1, -1, -1):
            if orders[i].id == order_id:
                del orders[i]
                self.order_ids.remove(order_id)
                break

    @typechecked
    def insert(self, order: Order):
        orders = order.side.choice(buy=self.buy_orders, sell=self.sell_orders)
        i = 0
        for i in range(len(orders) - 1, -1, -1):
            o = orders[i]
            if order.side.choice(
                buy=o.price < order.price, sell=o.price > order.price,
            ):
                i += 1
                break
        orders.insert(i, order)
        self.add_to_merged_orders(order.side, order.price, order.volume)
        self.order_ids.add(order.id)

    @typechecked
    def add_to_merged_orders(
        self, side: OrderSide, price: decimal.Decimal, volume: decimal.Decimal,
    ):
        merged_orders = side.choice(
            buy=self.merged_buy_orders, sell=self.merged_sell_orders,
        )
        previous_volume = merged_orders.get(price, 0)
        merged_orders[price] = previous_volume + volume
        if merged_orders[price] == 0:
            del merged_orders[price]

    @property
    def serialized_merged_orders(self):
        limit = 10
        sell_orders = self.merged_sell_orders
        buy_orders = self.merged_buy_orders
        sell_prices = sorted(sell_orders)[:limit]
        buy_prices = sorted(buy_orders)[-limit:]
        return {
            'sell': [[str(p), str(sell_orders[p])] for p in sell_prices],
            'buy': [[str(p), str(buy_orders[p])] for p in buy_prices],
        }

    @property
    def base_currency(self):
        return self.market.base_currency

    @property
    def quote_currency(self):
        return self.market.quote_currency

    @property
    def mq_queue_name(self):
        return get_mq_queue_name(self.pair)

    def fetch_orders(self):
        self.sell_orders = []
        self.buy_orders = []
        self.order_ids = set()
        self.merged_sell_orders = {}
        self.merged_buy_orders = {}
        orders = self.session.query(Order).filter(
            Order.active,
            Order.pair == self.pair,
        ).options(
            joinedload(Order.user, innerjoin=True),
        )
        for order in orders:
            if order.side is OrderSide.sell:
                self.sell_orders.append(order)
            else:
                self.buy_orders.append(order)
            self.add_to_merged_orders(
                order.side, order.price, order.remaining_volume,
            )
            self.order_ids.add(order.id)
        self.sell_orders.sort(key=lambda key: key.created_at)
        self.sell_orders.sort(key=lambda key: key.price, reverse=True)
        self.buy_orders.sort(key=lambda key: key.created_at)
        self.buy_orders.sort(key=lambda key: key.price)

    def fetch_candles(self):
        Candle.update_lack_candles(session=self.session, pair=self.pair)
        self.session.commit()
        self.candles = Candle.fetch_last_candles(
            session=self.session, pair=self.pair,
        )
        for candle in self.candles.values():
            if candle:
                self.session.expunge(candle)

    @contextlib.contextmanager
    def context(self, pair: str):
        try:
            self.session = create_session(self.app)
            self.session.expire_on_commit = False
            self.session.autoflush = False
            self.market = self.session.query(
                Market
            ).filter(
                Market.pair == pair,
            ).with_for_update(
                skip_locked=True,
            ).first()
            if not self.market:
                raise ValueError(f'OrderBook {pair} has been locked')
            print(f'Market: {self.pair}')
            print(f'Market: {self.pair}; Fetching orders…')
            self.fetch_orders()
            print(f'Market: {self.pair}; Fetching candles…')
            self.fetch_candles()
            print(f'Market: {self.pair}; Ready')
            self.mq_connection = get_mq_connection(self.app)
            self.mq_channel = get_mq_channel(
                self.mq_connection, self.mq_queue_name,
            )
            self.executor = concurrent.futures.thread.ThreadPoolExecutor(1)
            yield
        finally:
            if self.session:
                self.session.close()
                self.session = None
            self.market = None
            if self.executor:
                self.executor.shutdown(wait=False)
                self.executor = None
            if self.mq_channel:
                self.mq_channel.close()
                self.mq_channel = None
            if self.mq_connection:
                self.mq_connection.close()
                self.mq_connection = None

    def run(self):
        import time
        t = time.time()
        i = 0
        times = []
        p = 0
        import cProfile
        profile = cProfile.Profile()
        while True:
            consumer = self.mq_channel.consume(
                self.mq_queue_name, inactivity_timeout=1
            )
            for method, properties, body in consumer:
                if not body:
                    break
                if p == 0:
                    profile.enable()
                _t = time.time()
                self.session.begin_nested()
                payload = json.loads(body)
                type_ = payload['type']
                if type_ == 'cancel':
                    order_ids = [uuid.UUID(id_) for id_ in payload['order_ids']]
                    self.process_cancel_order(order_ids=order_ids)
                else:
                    order = parse_order(payload['order'])
                    self.process_place_order(order=order)
                self.session.commit()
                self.mq_channel.basic_ack(delivery_tag=method.delivery_tag)
                i += 1
                times.append(time.time() - _t)
                if time.time() - t >= 1:
                    speed = i * (time.time() - t)
                    high_t = max(times)
                    low_t = min(times)
                    avg_t = sum(times) / len(times)
                    actual_speed = 1 / avg_t
                    times = []
                    print(
                        f'Order processing speed: '
                        f'{speed:.2f}/s ({actual_speed:.2f}/s), '
                        f'highest {high_t:.4f}, '
                        f'lowest {low_t:.4f}, '
                        f'average {avg_t:.4f}'
                    )
                    t = time.time()
                    i = 0
                p += 1
                if p % 100 == 0:
                    profile.create_stats()
                    # profile.print_stats('cumtime')
            else:
                break

    @typechecked
    def process_place_order(
        self,
        order: Order,
    ):
        if order.volume * order.price < self.market.minimum_order_amount:
            return
        if order.id in self.order_ids:
            return
        self.session.add(order)
        try:
            result = self.match_order(order)
            trades = result['trades']
            balances = result['balances']
            self.session.commit()
            balance_map = {}
            for (user_id, currency), balance in balances.items():
                balance_map.setdefault(user_id, {})[currency] = balance
            websocket_messages = [
                {
                    'type': 'order',
                    'data': {
                        'pair': self.pair,
                        'book': self.serialized_merged_orders,
                    },
                },
                {
                    'type': 'balance',
                    'data': serialize(balance_map),
                },
            ]
            if trades:
                websocket_messages.append({
                    'type': 'trade',
                    'data': [
                        serialize({
                            'id': trade['id'],
                            'pair': order.pair,
                            'created_at': order.created_at,
                            'side': trade['side'],
                            'volume': trade['volume'],
                            'price': trade['price'],
                        })
                        for trade in trades
                    ],
                })
                if self.market.current_price != trades[-1]['price']:
                    self.market.current_price = trades[-1]['price']
                    websocket_messages.append({
                        'type': 'market',
                        'data': serialize([{
                            'pair': self.market.pair,
                            'currentPrice': self.market.current_price,
                        }]),
                    })
                    self.session.commit()
                self.process_candles(trades)
            self.send_websocket_messages(websocket_messages)
        except NotEnoughBalance as e:
            print('NotEnoughBalance')
            self.session.rollback()
            self.fetch_orders()
            return
        except (FlushError, IntegrityError) as e:
            print(type(e), str(e))
            self.session.rollback()
            self.fetch_orders()
            return
        except Exception as e:
            print(type(e), str(e))
            self.session.rollback()
            self.fetch_orders()
            return

    @typechecked
    def process_candles(self, trades: List[Mapping[str, Any]]):
        for unit_key in Candle.available_units:
            candle = self.candles[unit_key]
            if candle:
                cumulative_count = getattr(candle, '_cumulative_count', 0) + 1
                if cumulative_count >= 100:
                    self.session.add(candle)
                    self.session.commit()
                    self.session.expunge(candle)
                    cumulative_count = 0
                setattr(candle, '_cumulative_count', cumulative_count)
            for trade in trades:
                volume = trade['volume']
                price = trade['price']
                quote_volume = price * volume
                traded_at = trade['created_at']
                if candle and traded_at < candle.next_timestamp:
                    candle.update(price, volume, traded_at)
                else:
                    timestamp = Candle.get_timestamp_of(
                        traded_at, unit_key=unit_key,
                    )
                    if candle:
                        self.session.add(candle)
                        self.session.commit()
                        self.session.expunge(candle)
                    candle = Candle(
                        pair=self.pair, unit_key=unit_key,
                        timestamp=timestamp, updated_at=traded_at,
                        price=price, volume=volume, quote_volume=quote_volume,
                    )
                    self.candles[unit_key] = candle

    @typechecked
    def process_cancel_order(
        self,
        order_ids: List[uuid.UUID],
    ) -> None:
        result = self.session.execute(
            Order.__table__.update().where(
                Order.active &
                Order.id.in_(order_ids),
            ).values({
                'canceled_at': utcnow(),
            }).returning(
                Order.user_id,
                Order.locking_currency,
                Order.remaining_locked_amount,
            )
        ).fetchall()
        balance_keys = {
            (user_id, locking_currency)
            for user_id, locking_currency, _ in result
        }
        balances = {
            (t.user_id, t.currency): t
            for t in self.session.query(Balance).filter(
                tuple_(Balance.user_id, Balance.currency).in_(balance_keys)
            ).with_for_update()
        }
        for user_id, locking_currency, locked_amount in result:
            balance = balances.get((user_id, locking_currency))
            balance.locked_amount -= locked_amount
            setattr(balance, '_no_orm_events', True)
        self.session.commit()
        for order in itertools.chain(self.sell_orders, self.buy_orders):
            if order.id in order_ids:
                self.add_to_merged_orders(
                    order.side, order.price, -order.remaining_volume,
                )
        self.buy_orders = [
            o for o in self.buy_orders if o.id not in order_ids
        ]
        self.sell_orders = [
            o for o in self.sell_orders if o.id not in order_ids
        ]
        balance_map = {}
        for (user_id, currency), balance in balances.items():
            balance_map.setdefault(user_id, {})[currency] = balance
        self.send_websocket_messages([
            {
                'type': 'order',
                'data': {
                    'pair': self.pair,
                    'book': self.serialized_merged_orders,
                },
            },
            {
                'type': 'balance',
                'data': serialize(balance_map),
            },
        ])
        print(f'Canceled {list(map(str, order_ids))}')

    def match_order(self, new_order: Order):
        orders = list(
            new_order.side.choice(buy=self.sell_orders, sell=self.buy_orders)
        )
        self.insert(new_order)
        trades = []
        transactions = []
        trade_transactions = []
        now = datetime.datetime.now(datetime.timezone.utc)
        for order in reversed(orders):
            if not (~new_order.side).compare_op(order.price, new_order.price):
                break
            trade_volume = min(order.remaining_volume,
                               new_order.remaining_volume)
            if not trade_volume:
                raise ValueError(
                    f'trade_volume is zero! {new_order.id} {order.id}'
                )
            if new_order.side is OrderSide.buy:
                buy_order, sell_order = new_order, order
            else:
                buy_order, sell_order = order, new_order
            trade = {
                'id': uuid.uuid4(),
                'created_at': now,
                'buy_order': buy_order,
                'sell_order': sell_order,
                'side': new_order.side,
                'volume': trade_volume,
                'price': order.price,
                'base_currency': new_order.base_currency,
                'quote_currency': new_order.quote_currency,
                'index': len(trades),
            }
            trades.append(trade)
            new_transactions, new_trade_transactions = create_transactions(
                trade,
                maker_fee=self.market.maker_fee,
                taker_fee=self.market.taker_fee,
                now=now,
            )
            transactions += new_transactions
            trade_transactions += new_trade_transactions
            new_order.remaining_volume -= trade_volume
            order.remaining_volume -= trade_volume
            self.add_to_merged_orders(
                new_order.side, new_order.price, -trade_volume
            )
            self.add_to_merged_orders(
                order.side, order.price, -trade_volume
            )
            if order.remaining_volume == 0:
                order.mark_as_filled()
                self.remove(order.side, order.id)
            if new_order.remaining_volume == 0:
                new_order.mark_as_filled()
                self.remove(new_order.side, new_order.id)
                break
        balance_keys = {(t['user_id'], t['currency']) for t in transactions}
        balance_keys.add((new_order.user_id, new_order.locking_currency))
        balances = Balance.get_or_create_bulk(
            self.session, balance_keys, lock=True,
        )
        balance = balances[(new_order.user_id, new_order.locking_currency)]
        balance.locked_amount += new_order.locked_amount
        for balance in balances.values():
            setattr(balance, '_no_orm_events', True)
        for trade in trades:
            buy_order = trade.pop('buy_order')
            sell_order = trade.pop('sell_order')
            trade['buy_order_id'] = buy_order.id
            trade['sell_order_id'] = sell_order.id
            buyer_balance = balances[
                (buy_order.user_id, new_order.quote_currency)
            ]
            buyer_balance.locked_amount -= trade['volume'] * buy_order.price
            seller_balance = balances[
                (sell_order.user_id, new_order.base_currency)]
            seller_balance.locked_amount -= trade['volume']
        for transaction in transactions:
            balance = balances[
                (transaction['user_id'], transaction['currency'])]
            balance.amount += transaction['amount']
        if trades:
            self.session.flush()
            inserts = [
                (Trade, trades),
                (Transaction, transactions),
                (TradeTransaction, trade_transactions),
            ]
            for table, values in inserts:
                self.session.execute(table.__table__.insert().values(values))
        return {'trades': trades, 'balances': balances}

    async def async_send_websocket_messages(self, messages):
        websocket_url = self.app.config['APP_CONFIG']['websocket']['url']
        async with connect(websocket_url) as websocket:
            await websocket.send(json.dumps(messages))

    def _send_websocket_messages(self, messages):
        asyncio.run(self.async_send_websocket_messages(messages))

    def send_websocket_messages(self, messages):
        self.executor.submit(self._send_websocket_messages, messages)


@typechecked
def create_transactions(
    trade: Mapping[str, Any],
    *,
    maker_fee: decimal.Decimal,
    taker_fee: decimal.Decimal,
    now: datetime.datetime,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    fee = {
        'sell': trade['side'].choice(sell=taker_fee, buy=maker_fee),
        'buy': trade['side'].choice(buy=taker_fee, sell=maker_fee),
    }
    transactions = [
        {
            'user_id': trade['sell_order'].user_id,
            'currency': trade['quote_currency'],
            'amount': trade['volume'] * trade['price'] * (1 - fee['sell']),
        },
        {
            'user_id': uuid.UUID(int=0),
            'currency': trade['quote_currency'],
            'amount': trade['volume'] * trade['price'] * fee['sell'],
        },
        {
            'user_id': trade['sell_order'].user_id,
            'currency': trade['base_currency'],
            'amount': -trade['volume'],
        },
        {
            'user_id': trade['buy_order'].user_id,
            'currency': trade['quote_currency'],
            'amount': -trade['volume'] * trade['price'],
        },
        {
            'user_id': trade['buy_order'].user_id,
            'currency': trade['base_currency'],
            'amount': trade['volume'] * (1 - fee['buy']),
        },
        {
            'user_id': uuid.UUID(int=0),
            'currency': trade['base_currency'],
            'amount': trade['volume'] * fee['buy'],
        },
    ]
    for transaction in transactions:
        transaction['id'] = uuid.uuid4()
        transaction['created_at'] = now
        transaction['type'] = TransactionType.trade
    trade_transactions = [
        {'id': transaction['id'], 'trade_id': trade['id']}
        for transaction in transactions
    ]
    return transactions, trade_transactions
