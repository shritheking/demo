from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ProductBase(BaseModel):
    type: str
    name: str
    price: float
    duration: int
    active: bool = True
    description: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    type: Optional[str] = None
    name: Optional[str] = None
    price: Optional[float] = None
    duration: Optional[int] = None
    active: Optional[bool] = None
    description: Optional[str] = None

class ProductResponse(ProductBase):
    id: int
    
    class Config:
        from_attributes = True

class OrderBase(BaseModel):
    product_id: int
    order_type: str
    mt5_id: Optional[str] = None

class OrderCreate(OrderBase):
    user_id: int

class OrderResponse(OrderBase):
    id: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class PaymentCreate(BaseModel):
    order_id: int
    amount: float
    
class PaymentResponse(BaseModel):
    id: int
    razorpay_order_id: str
    payment_id: Optional[str]
    amount: float
    status: str
    
    class Config:
        from_attributes = True

class CompileJobResponse(BaseModel):
    id: int
    license_id: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class OrderFulfillmentRequest(BaseModel):
    mt5_id: Optional[str] = None
