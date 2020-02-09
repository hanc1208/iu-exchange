#!/usr/bin/env bash
dropdb iu-exchange
createdb iu-exchange
python manage.py -c dev.toml db upgrade head
python fetch_currencies.py
