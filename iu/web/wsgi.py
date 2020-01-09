import json
from typing import Any, Mapping

from flask import Flask
from typeguard import typechecked

from ..context import session
from ..orm import Base, migrate
from ..serializer import serialize


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
    app.json_encoder = JSONEncoder
    migrate.init_app(app, Base)

    @app.teardown_request
    def close_session(_):
        session.close()

    @app.route('/')
    @typechecked
    def hello_world() -> str:
        return 'Hello, world!'

    return app
