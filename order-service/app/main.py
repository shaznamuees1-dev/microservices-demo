from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, engine
from app import models, schemas, auth
import pika
import json
import os

def publish_order_created(order_id: int, user_id: str, item: str, quantity: int):
    try:
        rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        channel = connection.channel()

        # Declare exchange and queue
        channel.exchange_declare(exchange='orders', exchange_type='topic', durable=True)
        channel.queue_declare(queue='notifications', durable=True)
        channel.queue_bind(exchange='orders', queue='notifications', routing_key='order.created')

        # Publish message
        message = json.dumps({
            'event': 'OrderCreated',
            'order_id': order_id,
            'user_id': user_id,
            'item': item,
            'quantity': quantity
        })

        channel.basic_publish(
            exchange='orders',
            routing_key='order.created',
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)  # persistent message
        )

        connection.close()
        print(f'Published OrderCreated event for order {order_id}')
    except Exception as e:
        print(f'Failed to publish event: {e}')

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title='Order Service')

@app.get('/')
def health():
    return {'status': 'order-service running'}

@app.post('/orders', response_model=schemas.OrderResponse, status_code=201)
def create_order(
    order: schemas.OrderCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    new_order = models.Order(
        user_id=current_user['sub'],
        item=order.item,
        quantity=order.quantity
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    publish_order_created(new_order.id, new_order.user_id, new_order.item, new_order.quantity)
    return new_order

@app.get('/orders', response_model=list[schemas.OrderResponse])
def get_orders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    return db.query(models.Order).filter(
        models.Order.user_id == current_user['sub']
    ).all()

@app.get('/orders/{order_id}', response_model=schemas.OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.user_id == current_user['sub']
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')
    return order

@app.delete('/orders/{order_id}', status_code=204)
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.user_id == current_user['sub']
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')
    db.delete(order)
    db.commit()
