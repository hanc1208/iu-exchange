from typing import Union

from flask_migrate import Migrate
from sqlalchemy.engine import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session as SQLAlchemySession, sessionmaker
from typeguard import typechecked
from werkzeug.local import LocalProxy

Session = sessionmaker()
SessionType = Union[SQLAlchemySession, LocalProxy]
Base = declarative_base()

migrate = Migrate()


@typechecked
def create_session(app) -> SQLAlchemySession:
    options = app.config['APP_CONFIG']['database'].copy()
    url = options.pop('url')
    bind = create_engine(url, **options)
    return Session(bind=bind)
