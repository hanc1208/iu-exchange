#!/usr/bin/env python
import argparse
import time
import threading
import pathlib

import toml
import traceback

from iu.order_book.book import OrderBook
from iu.web.wsgi import create_wsgi_app

parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument('-c', '--config', type=pathlib.Path)


class OrderBookThread(threading.Thread):

    def __init__(self, app, pair: str):
        super().__init__()
        self.app = app
        self.pair = pair
        self.alive = True
        self.order_book = None

    def kill(self):
        self.alive = False
        if self.order_book.mq_channel:
            self.order_book.mq_channel.cancel()

    def run(self):
        self.order_book = OrderBook(self.app)
        while self.alive:
            try:
                with self.order_book.context(self.pair):
                    self.order_book.run()
            except Exception:
                print('closing')
                traceback.print_exc()
                time.sleep(1)


def main():
    args = parser.parse_args()
    with open(args.config) as f:
        config = toml.load(f)
    app = create_wsgi_app(config)
    if True:
        from iu.market import Market
        from iu.orm import create_session

        session = create_session(app)
        pairs = [pair for pair, in session.query(Market.pair)]
        threads = []
        for pair in pairs:
            thread = OrderBookThread(app, pair)
            thread.start()
            threads.append(thread)
        while any(t.isAlive() for t in threads):
            try:
                for t in threads:
                    t.join()
            except KeyboardInterrupt:
                for t in threads:
                    t.kill()
        return
    run_order_book_forever(app)


if __name__ == '__main__':
    main()
