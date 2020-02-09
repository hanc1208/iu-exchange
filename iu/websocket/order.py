import asyncio
import datetime
from dataclasses import dataclass, field
import itertools
import json
import time
import traceback
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set

from flask_login.utils import current_user
from sqlalchemy.sql.functions import rank, sum as sqlsum
from typeguard import typechecked
from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServerProtocol

from ..balance import Balance
from ..candle import Candle
from ..market import Market
from ..order import Order, OrderSide
from ..serializer import serialize
from ..trade import Trade
from .base import BaseWebSocketServer


@dataclass
class Client:
    websocket: WebSocketServerProtocol
    user_id: Optional[str] = None
    market: Optional[str] = None

    def __hash__(self):
        return self.websocket.__hash__()


class OrderWebSocketServer(BaseWebSocketServer):

    order_lock_time = 0.25
    order_locks: Dict[str, Optional[Mapping[str, Any]]] = (
        field(default_factory=dict)
    )
    balance_lock_time = 0.25
    balance_locks: Optional[Dict[str, Dict[str, Any]]] = None
    market_lock_time = 0.25
    market_locks: Optional[Dict[str, Dict[str, Any]]] = None
    trade_lock_time = 0
    trade_locks: Optional[Sequence[Dict[str, Any]]] = None
    market_clients_map: Dict[str, Set[Client]] = field(default_factory=dict)
    user_id_client_map: Dict[str, Set[Client]] = field(default_factory=dict)
    anonymous_clients: Set[Client] = field(default_factory=set)
    markets_cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    trades_cache: Dict[str, List[Mapping[str, Any]]] = field(
        default_factory=dict,
    )

    def __enter__(self):
        rv = super().__enter__()
        self.order_locks = {}
        self.balance_locks = None
        self.market_locks = None
        self.trade_locks = None
        self.market_clients_map = {}
        self.user_id_client_map = {}
        self.anonymous_clients = set()
        print('Caching markets…')
        self.markets_cache = self.get_markets()
        print('Caching trades…')
        self.trades_cache = self.get_trades(count=14)
        asyncio.ensure_future(self.periodically_fetch_markets())
        print('Server is running…')
        return rv

    async def periodically_fetch_markets(self):
        while True:
            await asyncio.sleep(60)
            self.markets_cache = self.get_markets()
            data = list(self.markets_cache.values())
            await self.send(self.clients, 'market', data)

    @property
    @typechecked
    def clients(self) -> Iterable[Client]:
        return itertools.chain(
            itertools.chain.from_iterable(self.user_id_client_map.values()),
            self.anonymous_clients,
        )

    @typechecked
    def close(self, client: Client):
        if client.user_id:
            try:
                self.user_id_client_map[client.user_id].remove(client)
            except KeyError:
                pass
        else:
            try:
                self.anonymous_clients.remove(client)
            except KeyError:
                pass
        if client.market:
            try:
                self.market_clients_map[client.market].remove(client)
            except KeyError:
                pass

    @typechecked
    async def send(
        self,
        clients: Iterable[Client], type_: str, data, *, silent: bool=True,
    ):
        clients = list(clients)
        if not clients:
            return

        async def _send(client: Client):
            try:
                await client.websocket.send(payload)
            except ConnectionClosed:
                if not silent:
                    raise
                self.close(client)

        payload = json.dumps({'type': type_, 'data': data})
        await asyncio.wait([_send(client) for client in clients])

    @typechecked
    def get_balances(self, user_id: str) -> Mapping[str, Mapping[str, Any]]:
        return {
            balance.currency: serialize(balance)
            for balance in self.session.query(Balance).filter(
                Balance.user_id == user_id,
            )
        }

    @typechecked
    def get_markets(self) -> Dict[str, Mapping[str, Any]]:
        result = {}
        for market in self.session.query(Market):
            candle = Candle.get_daily_candle(self.session, market.pair)
            serialized = serialize(market)
            serialized.update(
                serialize({
                    'dayVolume': candle.quote_volume if candle else '0',
                    'open': candle.open if candle else '0',
                    'high': candle.high if candle else '0',
                    'low': candle.low if candle else '0',
                    'close': candle.close if candle else '0',
                })
            )
            result[market.pair] = serialized
        return result

    @typechecked
    def get_trades(self, *, count: int) -> Dict[str, List[Mapping[str, Any]]]:
        _rank = rank().over(
            partition_by=Trade.pair,
            order_by=(Trade.created_at.desc(), Trade.index.desc()),
        )
        query = self.session.query(
            Trade, _rank
        ).from_self().order_by(Trade.pair, _rank).filter(_rank <= count)
        trades = {}
        for trade, _rank in query:
            trades.setdefault(trade.pair, []).append(serialize(trade))
        trades = {pair: list(reversed(t)) for pair, t in trades.items()}
        return trades

    @typechecked
    def get_order_book(self, pair: str) -> Mapping[str, List[List[str]]]:
        limit = 8
        query = self.session.query(
            Order.price, sqlsum(Order.remaining_volume)
        ).filter(
            Order.pair == pair,
            Order.active,
        ).group_by(
            Order.price
        )
        buy_orders = query.filter(
            Order.side == OrderSide.buy
        ).order_by(
            OrderSide.buy.order_op(Order.price)
        ).limit(limit)
        sell_orders = query.filter(
            Order.side == OrderSide.sell
        ).order_by(
            OrderSide.sell.order_op(Order.price)
        ).limit(limit)
        data = {
            'buy': [[str(p), str(v)] for p, v in buy_orders],
            'sell': [[str(p), str(v)] for p, v in sell_orders],
        }
        return data

    @typechecked
    def get_user_id(self, websocket: WebSocketServerProtocol) -> Optional[str]:
        user_id = None
        headers = websocket.request_headers
        with self.app.test_request_context(headers=headers.items()):
            if current_user and current_user.is_authenticated:
                user_id = str(current_user.id)
        return user_id

    @typechecked
    async def subscribe(self, websocket: WebSocketServerProtocol):
        user_id = self.get_user_id(websocket)
        client = Client(websocket=websocket, user_id=user_id)
        if user_id:
            self.user_id_client_map.setdefault(user_id, set()).add(client)
        else:
            self.anonymous_clients.add(client)
        try:
            await self.send(
                [client], 'market', list(self.markets_cache.values()),
                silent=False,
            )
            if user_id:
                await self.send(
                    [client], 'balance', self.get_balances(user_id),
                    silent=False,
                )
            async for message in websocket:
                payload = json.loads(message)
                if payload['type'] == 'subscribeMarket':
                    market = payload['data']
                    await self.subscribe_market(client, market)
        except ConnectionClosed:
            pass
        finally:
            self.close(client)

    @typechecked
    async def subscribe_market(self, client: Client, market: str):
        if client.market:
            self.market_clients_map[client.market].remove(client)
        self.market_clients_map.setdefault(market, set()).add(client)
        client.market = market
        order_book = self.get_order_book(market)
        await asyncio.wait([
            self.send([client], 'order', order_book, silent=False),
            self.send(
                [client], 'trade', self.trades_cache.get(market, []),
                silent=False,
            ),
        ])

    def select_publisher(self, type_):
        return {
            'balance': self.publish_balance,
            'market': self.publish_market,
            'order': self.publish_order,
            'trade': self.publish_trade,
        }.get(type_)

    @typechecked
    async def publish(self, websocket: WebSocketServerProtocol):
        async for message in websocket:
            payloads = json.loads(message)
            if not isinstance(payloads, list):
                payloads = [payloads]
            futures = []
            for payload in payloads:
                try:
                    type_ = payload['type']
                    data = payload['data']
                except KeyError:
                    print(payload)
                    continue
                publisher = self.select_publisher(type_)
                if not publisher:
                    print(payload)
                    continue
                futures.append(publisher(data))
            await asyncio.gather(*futures)

    @typechecked
    async def publish_balance(self, data: Mapping[str, Mapping[str, Any]]):
        if self.balance_locks is not None:
            self.balance_locks = self.balance_locks or {}
            for user_id, payload in data.items():
                self.balance_locks.setdefault(user_id, {}).update(payload)
            return
        self.balance_locks = False
        try:
            t = time.time()
            futures = []
            for user_id, payload in data.items():
                clients = self.user_id_client_map.get(user_id, set())
                futures.append(self.send(clients, 'balance', payload))
            await asyncio.wait(futures)
            await asyncio.sleep(
                max(0.0, self.balance_lock_time - (time.time() - t))
            )
            require_publish = self.balance_locks
        finally:
            self.balance_locks = None
        if isinstance(require_publish, dict):
            await self.publish_balance(require_publish)

    @typechecked
    async def publish_market(self, data: Sequence[Dict[str, Any]]):
        if self.market_locks is not None:
            self.market_locks = self.market_locks or {}
            self.market_locks.update({
                market['pair']: market for market in data
            })
            return
        self.market_locks = False
        try:
            t = time.time()
            for market in data:
                self.markets_cache[market['pair']].update(market)
            await self.send(self.clients, 'market', data)
            await asyncio.sleep(
                max(0.0, self.market_lock_time - (time.time() - t))
            )
            require_publish = self.market_locks
        finally:
            self.market_locks = None
        if isinstance(require_publish, dict):
            await self.publish_market(list(require_publish.values()))

    @typechecked
    async def publish_order(self, data: Mapping[str, Any]):
        pair = data['pair']
        book = data['book']
        if pair in self.order_locks:
            self.order_locks[pair] = data
            return
        self.order_locks[pair] = None
        try:
            t = time.time()
            clients = self.market_clients_map.get(pair, set())
            await self.send(clients, 'order', book, silent=True)
            await asyncio.sleep(
                max(0.0, self.order_lock_time - (time.time() - t))
            )
            require_publish = self.order_locks[pair]
        finally:
            del self.order_locks[pair]
        if require_publish:
            await self.publish_order(require_publish)

    @typechecked
    async def publish_trade(self, data: Sequence[Mapping[str, Any]]):
        if self.trade_locks is not None:
            self.trade_locks = self.trade_locks or []
            self.trade_locks.extend(data)
            return
        self.trade_locks = False
        pair_trades_map = {}
        for payload in data:
            pair = payload['pair']
            pair_trades_map.setdefault(pair, []).append(payload)
        try:
            t = time.time()
            futures = []
            for pair, trades in pair_trades_map.items():
                clients = self.market_clients_map.get(pair, set())
                cache = self.trades_cache.setdefault(pair, [])
                cache.extend(trades)
                if len(cache) > 15:
                    self.trades_cache[pair] = cache[-15:]
                futures.append(self.send(clients, 'trade', trades, silent=True))
            await asyncio.wait(futures)
            await asyncio.sleep(
                max(0.0, self.trade_lock_time - (time.time() - t))
            )
            require_publish = self.trade_locks
        finally:
            self.trade_locks = None
        if isinstance(require_publish, list):
            await self.publish_trade(require_publish)

    @typechecked
    async def __call__(self, websocket: WebSocketServerProtocol, path: str):
        try:
            if path == '/subscribe/':
                await self.subscribe(websocket)
            elif path == '/publish/':
                await self.publish(websocket)
            else:
                return
        except Exception:
            self.session.rollback()
            traceback.print_exc()
        finally:
            websocket.close()
