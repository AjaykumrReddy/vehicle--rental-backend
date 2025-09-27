from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Dict, Any
from ..db import get_db
from ..auth import get_current_user
from .schemas import CreatePaymentRequest, PaymentOrderResponse, VerifyPaymentRequest, PaymentResponse, RefundRequest
from .service import PaymentService
from .models import Payment
import json

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/create-order", response_model=PaymentOrderResponse)
async def create_payment_order(
    request: CreatePaymentRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create Razorpay order for booking payment"""
    print("Received request data:", request)
    try:
        user_id = UUID(current_user["user_id"])
        payment_service = PaymentService(db)
        
        result = payment_service.create_payment_order(request, user_id)
        
        return PaymentOrderResponse(
            order_id=result["order_id"],
            amount=result["amount"],
            currency=result["currency"],
            key=result["key"]
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print("Error creating payment order:", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment order"
        )

@router.post("/verify")
async def verify_payment(
    request: VerifyPaymentRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify Razorpay payment and confirm booking"""
    try:
        user_id = UUID(current_user["user_id"])
        payment_service = PaymentService(db)
        
        result = payment_service.verify_payment(request, user_id)
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment verification failed"
        )

@router.post("/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Razorpay webhooks for payment status updates"""
    try:
        payload = await request.body()
        webhook_signature = request.headers.get("X-Razorpay-Signature")
        
        # Verify webhook signature (implement webhook signature verification)
        # For now, we'll process the webhook data
        
        event_data = json.loads(payload)
        event_type = event_data.get("event")
        
        if event_type == "payment.captured":
            payment_entity = event_data["payload"]["payment"]["entity"]
            order_id = payment_entity["order_id"]
            payment_id = payment_entity["id"]
            
            # Update payment status
            payment = db.query(Payment).filter(
                Payment.razorpay_order_id == order_id
            ).first()
            
            if payment and payment.status == "created":
                payment.razorpay_payment_id = payment_id
                payment.status = "paid"
                payment.payment_method = payment_entity.get("method")
                
                # Update booking
                booking = payment.booking
                booking.payment_status = "paid"
                booking.status = "confirmed"
                
                db.commit()
        
        elif event_type == "payment.failed":
            payment_entity = event_data["payload"]["payment"]["entity"]
            order_id = payment_entity["order_id"]
            
            # Update payment status
            payment = db.query(Payment).filter(
                Payment.razorpay_order_id == order_id
            ).first()
            
            if payment:
                payment.status = "failed"
                payment.failure_reason = payment_entity.get("error_description")
                db.commit()
        
        return {"status": "ok"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )

@router.get("/history", response_model=list[PaymentResponse])
async def get_payment_history(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's payment history"""
    try:
        user_id = UUID(current_user["user_id"])
        
        payments = db.query(Payment).filter(
            Payment.user_id == user_id
        ).order_by(Payment.created_at.desc()).all()
        
        return payments
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch payment history"
        )

@router.get("/status/{booking_id}")
async def get_payment_status(
    booking_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get payment status for a booking"""
    try:
        user_id = UUID(current_user["user_id"])
        
        payment = db.query(Payment).filter(
            Payment.booking_id == booking_id,
            Payment.user_id == user_id
        ).first()
        
        if not payment:
            return {"status": "not_found", "payment_required": True}
        
        return {
            "status": payment.status,
            "payment_id": str(payment.id),
            "amount": float(payment.amount),
            "currency": payment.currency,
            "payment_required": payment.status != "paid"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get payment status"
        )

@router.post("/refund")
async def process_refund(
    request: RefundRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Process refund for a payment (Admin/Owner only)"""
    try:
        # Add authorization check for admin/owner
        payment_service = PaymentService(db)
        
        result = payment_service.process_refund(
            request.payment_id,
            request.amount,
            request.reason
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Refund processing failed"
        )