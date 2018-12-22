import datetime
from typing import Any, Mapping

from flask import Flask
from ormeasy.sqlalchemy import test_connection
from pytest import fixture
from typeguard import typechecked

from iu.orm import Base, Session, SessionType, create_session
from iu.web.wsgi import create_wsgi_app


@fixture
@typechecked
def fx_config() -> Mapping[str, Any]:
    return {
        'web': {
            'SECRET_KEY': 'de775515f6a4cdca5edfd71c2a32193d',
        },
        'database': {
            'url': 'postgresql:///iu-exchange-test',
        },
    }


@fixture
def fx_wsgi_app(fx_config: Mapping[str, Any]) -> Flask:
    wsgi_app = create_wsgi_app(fx_config)
    with wsgi_app.app_context():
        yield wsgi_app


@fixture
@typechecked
def fx_utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


@fixture
def fx_session(fx_wsgi_app: Flask) -> SessionType:
    session = create_session(fx_wsgi_app)
    engine = session.bind
    with test_connection(fx_wsgi_app, Base.metadata, engine) as connection:
        yield Session(bind=connection)
