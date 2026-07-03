from pydantic import BaseModel
from datetime import datetime

class OrderCreate(BaseModel):
    item: str
    quantity: int

class OrderResponse(BaseModel):
    id: int
    user_id: str
    item: str
    quantity: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
