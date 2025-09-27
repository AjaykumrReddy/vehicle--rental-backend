import razorpay
import hmac
import hashlib
from typing import Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone
from ..models import Booking
from .models import Payment
from .schemas import CreatePaymentRequest, VerifyPaymentRequest
import os

class RazorpayService:
    def __init__(self):
        self.key_id = os.getenv("RAZORPAY_KEY_ID")
        self.key_secret = os.getenv("RAZORPAY_KEY_SECRET")
        
        print(f"Razorpay Key ID: {self.key_id}")
        print(f"Razorpay Key Secret: {'*' * len(self.key_secret) if self.key_secret else None}")
        
        if not self.key_id or not self.key_secret:
            raise ValueError("Razorpay credentials not found in environment variables")
        
        try:
            self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
            print("Razorpay client initialized successfully")
        except Exception as e:
            print(f"Razorpay client initialization failed: {e}")
            raise
    
    def create_order(self, amount: float, currency: str = "INR", receipt: str = None) -> Dict[str, Any]:
        """Create Razorpay order"""
        amount_paise = int(amount * 100)  # Convert to paise
        
        order_data = {
            "amount": amount_paise,
            "currency": currency,
            "receipt": receipt or f"order_{datetime.now().timestamp()}",
            "payment_capture": 1  # Auto capture
        }
        
        return self.client.order.create(data=order_data)
    
    def verify_signature(self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        """Verify Razorpay payment signature"""
        generated_signature = hmac.new(
            self.key_secret.encode(),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(generated_signature, razorpay_signature)
    
    def get_payment_details(self, payment_id: str) -> Dict[str, Any]:
        """Get payment details from Razorpay"""
        return self.client.payment.fetch(payment_id)
    
    def create_refund(self, payment_id: str, amount: int = None) -> Dict[str, Any]:
        """Create refund for a payment"""
        refund_data = {}
        if amount:
            refund_data["amount"] = amount
        
        return self.client.payment.refund(payment_id, refund_data)

class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.razorpay = RazorpayService()
    
    def create_payment_order(self, request: CreatePaymentRequest, user_id: UUID) -> Dict[str, Any]:
        """Create payment order for booking"""
        # Verify booking exists and belongs to user
        booking = self.db.query(Booking).filter(
            Booking.id == request.booking_id,
            Booking.renter_id == user_id,
            Booking.payment_status == "pending"
        ).first()
        
        if not booking:
            raise ValueError("Booking not found or already paid")
        
        # Create Razorpay order
        razorpay_order = self.razorpay.create_order(
            amount=request.amount,
            currency=request.currency,
            receipt=f"bk_{str(request.booking_id)[:32]}"
        )
        
        # Save payment record
        payment = Payment(
            booking_id=request.booking_id,
            user_id=user_id,
            razorpay_order_id=razorpay_order["id"],
            amount=Decimal(str(request.amount)),
            currency=request.currency,
            status="created"
        )
        
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        
        return {
            "payment_id": str(payment.id),
            "order_id": razorpay_order["id"],
            "amount": razorpay_order["amount"],
            "currency": razorpay_order["currency"],
            "key": self.razorpay.key_id
        }
    
    def verify_payment(self, request: VerifyPaymentRequest, user_id: UUID) -> Dict[str, Any]:
        """Verify and confirm payment"""
        # Find payment record
        payment = self.db.query(Payment).filter(
            Payment.razorpay_order_id == request.razorpay_order_id,
            Payment.user_id == user_id
        ).first()
        
        if not payment:
            raise ValueError("Payment not found")
        
        # Verify signature
        if not self.razorpay.verify_signature(
            request.razorpay_order_id,
            request.razorpay_payment_id,
            request.razorpay_signature
        ):
            payment.status = "failed"
            payment.failure_reason = "Invalid signature"
            self.db.commit()
            raise ValueError("Payment verification failed")
        
        # Get payment details from Razorpay
        payment_details = self.razorpay.get_payment_details(request.razorpay_payment_id)
        
        # Update payment record
        payment.razorpay_payment_id = request.razorpay_payment_id
        payment.razorpay_signature = request.razorpay_signature
        payment.status = "paid"
        payment.payment_method = payment_details.get("method")
        payment.updated_at = datetime.now(timezone.utc)
        
        # Update booking status
        booking = payment.booking
        booking.payment_status = "paid"
        booking.payment_id = request.razorpay_payment_id
        booking.status = "confirmed"
        booking.confirmed_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        return {
            "success": True,
            "payment_id": str(payment.id),
            "booking_id": str(booking.id),
            "status": "confirmed"
        }
    
    def process_refund(self, payment_id: UUID, amount: float = None, reason: str = None) -> Dict[str, Any]:
        """Process refund for a payment"""
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        
        if not payment or payment.status != "paid":
            raise ValueError("Payment not found or not eligible for refund")
        
        refund_amount = amount or float(payment.amount)
        refund_amount_paise = int(refund_amount * 100)
        
        # Create refund in Razorpay
        refund = self.razorpay.create_refund(
            payment.razorpay_payment_id,
            refund_amount_paise
        )
        
        # Update payment record
        payment.status = "refunded"
        payment.refund_amount = Decimal(str(refund_amount))
        payment.refunded_at = datetime.now(timezone.utc)
        
        # Update booking
        booking = payment.booking
        booking.payment_status = "refunded"
        booking.status = "cancelled"
        booking.cancelled_at = datetime.now(timezone.utc)
        booking.cancellation_reason = reason or "Refund processed"
        
        self.db.commit()
        
        return {
            "success": True,
            "refund_id": refund["id"],
            "amount": refund_amount,
            "status": "refunded"
        }