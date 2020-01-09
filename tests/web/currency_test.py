import json
from typing import Mapping

from flask import Flask

from iu.currency import Currency
from iu.serializer import serialize


def test_fetch_currencies(
    fx_currencies: Mapping[str, Currency],
    fx_wsgi_app: Flask,
):
    url = '/currencies/'
    client = fx_wsgi_app.test_client()

    response = client.get(url)
    assert response.status_code == 200, response.get_data(as_text=True)
    expected = list(fx_currencies.values())
    assert response.get_json() == serialize(expected)
