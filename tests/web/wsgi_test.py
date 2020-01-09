import json
from typing import Any, Mapping
import uuid

from pytest import raises
from typeguard import typechecked

from iu.web.wsgi import create_wsgi_app, JSONEncoder


@typechecked
def test_json_encoder():
    hard_to_serialize = uuid.UUID('90ce88e3-8fe9-4d76-b84f-975ea47e9637')

    with raises(TypeError) as e:
        json.JSONEncoder().encode(hard_to_serialize)
    assert 'is not JSON serializable' in str(e.value)

    expected = '"90ce88e3-8fe9-4d76-b84f-975ea47e9637"'
    assert JSONEncoder().encode(hard_to_serialize) == expected

    with raises(TypeError) as e:
        assert JSONEncoder().encode(object())
    assert 'is not JSON serializable' in str(e.value)


@typechecked
def test_create_wsgi_app(fx_config: Mapping[str, Any]) -> None:
    fx_config['web']['__WEB_CONFIG__'] = '__WEB_CONFIG__'
    fx_config['__APP_CONFIG__'] = '__APP_CONFIG__'
    app = create_wsgi_app(fx_config)
    assert app.config['__WEB_CONFIG__'] == '__WEB_CONFIG__'
    assert app.config['APP_CONFIG']['__APP_CONFIG__'] == '__APP_CONFIG__'
    client = app.test_client()
    response = client.get('/').data.decode('utf-8')
    assert response == 'Hello, world!'
