from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, engine
from app import models, schemas, auth

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
