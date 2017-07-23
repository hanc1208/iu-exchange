#!/usr/bin/env python
from gevent.monkey import patch_all  # noqa
patch_all()  # noqa
import argparse
import os
import pathlib

from toml import load as toml_load
from gevent.pywsgi import WSGIServer

from app.web.wsgi import create_wsgi_app

parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument('-p', '--port', type=int,
                    default=int(os.environ.get('PORT', 8516)),
                    help='port number to listen')
parser.add_argument('-H', '--host', default='0.0.0.0')
parser.add_argument('-d', '--debug', action='store_true', default=False)
parser.add_argument('config', type=pathlib.Path)


def main():
    args = parser.parse_args()
    with open(args.config) as f:
        config = toml_load(f)
    app = create_wsgi_app(config)
    if args.debug:
        app.run(
            host=args.host, port=args.port, debug=args.debug, threaded=True,
        )
    else:
        server = WSGIServer((args.host, args.port), app)
        server.serve_forever()


if __name__ == '__main__':
    main()
