import pathlib

from flask import Flask
from flask_migrate import MigrateCommand
from flask_script import Manager
from toml import load
from typeguard import typechecked

from app.web.wsgi import create_wsgi_app


@typechecked
def manager_create_wsgi_app(config_path: pathlib.Path) -> Flask:
    with open(config_path) as f:
        config = load(f)
    app = create_wsgi_app(config)
    return app


if __name__ == "__main__":
    manager = Manager(manager_create_wsgi_app)
    manager.add_option('-c', '--config', dest='config_path', type=pathlib.Path)
    manager.add_command('db', MigrateCommand)
    manager.run()
