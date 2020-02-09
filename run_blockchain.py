#!/usr/bin/env python
import argparse
import logging
import pathlib
import threading
import time
import traceback

import toml

from iu.blockchain.bitcoin import BitcoinBlockchain
from iu.blockchain.ethereum import EthereumBlockchain
from iu.web.wsgi import create_wsgi_app

parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument('-c', '--config', type=pathlib.Path)
parser.add_argument('currency', type=str)


class BlockchainThread(threading.Thread):

    def __init__(self, app, currency: str):
        super().__init__()
        self.app = app
        self.currency = currency
        self.alive = True
        self.blockchain = None

    def kill(self):
        self.alive = False
        self.blockchain.alive = False

    def run(self):
        if self.currency == 'ETH':
            cls = EthereumBlockchain
        elif self.currency == 'BTC':
            cls = BitcoinBlockchain
        else:
            return
        self.blockchain = cls(self.app)
        while self.alive:
            try:
                with self.blockchain.context():
                    self.blockchain.sync()
            except Exception:
                print('closing')
                traceback.print_exc()
                time.sleep(1)


def main():
    args = parser.parse_args()
    with open(args.config) as f:
        config = toml.load(f)
    app = create_wsgi_app(config)
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger().setLevel(logging.INFO)
    if args.currency == 'ethereum':
        currency = 'ETH'
    else:
        currency = 'BTC'
    thread = BlockchainThread(app, currency)
    thread.start()
    while thread.is_alive():
        try:
            thread.join(1)
        except KeyboardInterrupt:
            thread.kill()


if __name__ == '__main__':
    main()

