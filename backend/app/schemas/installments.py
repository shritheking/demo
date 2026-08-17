from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class InstallmentCreate(BaseModel):
    order_id: int
    total_amount: float
    installment_amount: float
    installment_count: int
    first_payment_amount: float
    license_period_days: int

class InstallmentPaymentRecord(BaseModel):
    amount: float
    payment_number: int
    payment_date: datetime
    status: str

    class Config:
        from_attributes = True

class InstallmentCustomerResponse(BaseModel):
    order_id: int
    mt5_id: Optional[str]
    product_name: str
    total_amount: float
    installment_amount: float
    amount_paid: float
    amount_remaining: float
    installments_paid: int
    installment_count: int
    license_status: str
    license_expiry: Optional[datetime]
    next_due_date: Optional[datetime]
    installment_status: str
    license_period_days: Optional[int] = None
    payments: List[InstallmentPaymentRecord]

class InstallmentPayRequest(BaseModel):
    order_id: int
    amount: float
