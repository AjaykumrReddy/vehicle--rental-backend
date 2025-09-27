from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal

class CreatePaymentRequest(BaseModel):
    booking_id: UUID
    amount: float = Field(..., gt=0)
    currency: str = Field("INR", pattern="^[A-Z]{3}$")

class PaymentOrderResponse(BaseModel):
    order_id: str
    amount: int  # Amount in paise for Razorpay
    currency: str
    key: str  # Razorpay key for frontend

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class PaymentResponse(BaseModel):
    id: UUID
    booking_id: UUID
    razorpay_order_id: str
    razorpay_payment_id: Optional[str]
    amount: float
    currency: str
    status: str
    payment_method: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class RefundRequest(BaseModel):
    payment_id: UUID
    amount: Optional[float] = None  # Partial refund if specified
    reason: Optional[str] = None