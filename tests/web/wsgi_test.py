from typing import Any, Mapping

from typeguard import typechecked

from iu.web.wsgi import create_wsgi_app


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
