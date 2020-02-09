#!/usr/bin/env python
import argparse
import asyncio
import os
import pathlib

import toml
from websockets import serve

from iu.websocket.order import OrderWebSocketServer

parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument('-p', '--port', type=int,
                    default=int(os.environ.get('PORT', 8517)),
                    help='port number to listen')
parser.add_argument('-H', '--host', default='0.0.0.0')
parser.add_argument('-c', '--config', type=pathlib.Path)


def main():
    args = parser.parse_args()
    with open(args.config) as f:
        config = toml.load(f)
    with OrderWebSocketServer(config) as server:
        trade_server = serve(
            server, args.host, args.port,
            process_request=server.process_request,
        )
        asyncio.get_event_loop().run_until_complete(trade_server)
        asyncio.get_event_loop().run_forever()


if __name__ == '__main__':
    main()
