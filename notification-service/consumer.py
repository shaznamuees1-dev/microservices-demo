import pika
import json
import time
import os

RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
MAX_RETRIES = 3

def process_message(message: dict):
    print(f'Processing notification for order {message["order_id"]}: {message["item"]} x{message["quantity"]}')
    # In production: send email, SMS, push notification etc.
    # For now: just log it

def on_message(channel, method, properties, body):
    retry_count = 0
    if properties.headers:
        retry_count = properties.headers.get('x-retry-count', 0)

    try:
        message = json.loads(body)
        print(f'Received event: {message["event"]} (attempt {retry_count + 1})')
        process_message(message)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        print('Message processed successfully')

    except Exception as e:
        print(f'Error processing message: {e}')

        if retry_count < MAX_RETRIES:
            # Exponential backoff: 1s, 2s, 4s
            wait_time = 2 ** retry_count
            print(f'Retrying in {wait_time}s (attempt {retry_count + 1}/{MAX_RETRIES})')
            time.sleep(wait_time)

            # Republish with incremented retry count
            channel.basic_publish(
                exchange='orders',
                routing_key='order.created',
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    headers={'x-retry-count': retry_count + 1}
                )
            )
            channel.basic_ack(delivery_tag=method.delivery_tag)
        else:
            # Max retries exceeded - send to DLQ
            print(f'Max retries exceeded, sending to DLQ')
            channel.basic_publish(
                exchange='',
                routing_key='notifications.dlq',
                body=body,
                properties=pika.BasicProperties(delivery_mode=2)
            )
            channel.basic_ack(delivery_tag=method.delivery_tag)

def main():
    print('Notification service starting...')

    # Wait for RabbitMQ to be ready
    while True:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            break
        except Exception:
            print('Waiting for RabbitMQ...')
            time.sleep(3)

    channel = connection.channel()

    # Declare exchange, main queue, and DLQ
    channel.exchange_declare(exchange='orders', exchange_type='topic', durable=True)
    channel.queue_declare(queue='notifications', durable=True)
    channel.queue_bind(exchange='orders', queue='notifications', routing_key='order.created')
    channel.queue_declare(queue='notifications.dlq', durable=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='notifications', on_message_callback=on_message)

    print('Waiting for messages...')
    channel.start_consuming()

if __name__ == '__main__':
    main()
