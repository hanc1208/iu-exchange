import asyncio
import json
from typing import Any, Mapping

from flask import Flask, send_from_directory
from typeguard import typechecked
from websockets import connect
from werkzeug.wrappers import Response

from ..context import session, websocket_messages
from ..orm import Base, migrate
from ..serializer import serialize
from .balance import bp_balance
from .candle import bp_candle
from .currency import bp_currency
from .order import bp_order
from .transaction import bp_transaction
from .user import bp_user, login_manager


class JSONEncoder(json.JSONEncoder):

    def default(self, o):
        try:
            return serialize(o)
        except NotImplementedError:
            return super().default(o)


@typechecked
def create_wsgi_app(config: Mapping[str, Any]) -> Flask:
    app = Flask(__name__)
    app.config.update(config['web'])
    app.config['APP_CONFIG'] = config
    import os
    config['database']['url'] = (
        os.environ.get('DATABASE_URL') or config['database']['url']
    )
    app.json_encoder = JSONEncoder
    app.register_blueprint(bp_balance)
    app.register_blueprint(bp_candle)
    app.register_blueprint(bp_currency)
    app.register_blueprint(bp_order)
    app.register_blueprint(bp_transaction)
    app.register_blueprint(bp_user)
    migrate.init_app(app, Base)
    login_manager.init_app(app)

    @app.teardown_request
    def close_session(_):
        session.close()

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    @typechecked
    def hello_world(path: str) -> Response:
        response = send_from_directory('static/frontend', 'index.html')
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.must_revalidate = True
        return response

    @app.route('/static/<path:path>')
    def send_static(path):
        return send_from_directory('static', path)

    @app.teardown_request
    def send_websocket_messages(e):
        if not websocket_messages:
            return

        async def _send_websocket_messages():
            websocket_url = config['websocket']['url']
            async with connect(websocket_url) as websocket:
                await websocket.send(json.dumps(list(websocket_messages)))

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(_send_websocket_messages())

    return app
