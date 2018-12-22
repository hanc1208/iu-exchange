from flask import current_app, request
from typeguard import typechecked
from werkzeug.local import LocalProxy

from .orm import SessionType, create_session


@LocalProxy
@typechecked
def session() -> SessionType:
    try:
        return request._current_session
    except AttributeError:
        request._current_session = create_session(current_app)
        if hasattr(current_app, '_test_fx_connection'):
            request._current_session.bind = current_app._test_fx_connection
        return request._current_session
