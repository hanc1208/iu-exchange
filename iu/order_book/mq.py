import json
from typing import List

from pika.adapters.blocking_connection import (
    BlockingChannel, BlockingConnection,
)
from pika.connection import URLParameters
from typeguard import typechecked

from ..order import Order
from ..serializer import serialize


@typechecked
def get_mq_connection(app) -> BlockingConnection:
    url = app.config['APP_CONFIG'].get('amqp', {}).get('url')
    parameters = url and URLParameters(url)
    return BlockingConnection(parameters)


@typechecked
def get_mq_channel(
    mq_connection: BlockingConnection,
    mq_queue_name: str,
) -> BlockingChannel:
    mq_channel = mq_connection.channel()
    mq_channel.queue_declare(queue=mq_queue_name, durable=True)
    mq_channel.basic_qos(prefetch_count=1)
    return mq_channel


@typechecked
def get_mq_queue_name(pair: str) -> str:
    return f'order_book.{pair.lower()}'


@typechecked
def enqueue_place_order(app, order: Order):
    mq_queue_name = get_mq_queue_name(order.pair)
    with get_mq_connection(app) as mq_connection, \
            get_mq_channel(mq_connection, mq_queue_name) as mq_channel:
        mq_channel.basic_publish(
            exchange='',
            routing_key=f'order_book.{order.pair.lower()}',
            body=json.dumps({
                'type': 'place',
                'order': serialize(order),
            }),
        )


@typechecked
def enqueue_delete_order(app, orders: List[Order]):
    order_id_map = {}
    for order in orders:
        order_id_map.setdefault(order.pair, []).append(order.id)
    with get_mq_connection(app) as mq_connection:
        for pair, order_ids in order_id_map.items():
            mq_queue_name = get_mq_queue_name(pair)
            with get_mq_channel(mq_connection, mq_queue_name) as mq_channel:
                count = 100
                for i in range(0, len(order_ids), count):
                    mq_channel.basic_publish(
                        exchange='',
                        routing_key=f'order_book.{pair.lower()}',
                        body=json.dumps({
                            'type': 'cancel',
                            'order_ids': serialize(order_ids[i:i + count]),
                        }),
                    )
