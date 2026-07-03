from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base
from datetime import datetime

class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False)
    item = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
