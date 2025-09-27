from sqlalchemy import Column, String, Text, ForeignKey, Numeric, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..db import Base

class Payment(Base):
    __tablename__ = "payments"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'), index=True)
    booking_id = Column(UUID(as_uuid=True), ForeignKey('bookings.id'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    
    # Razorpay fields
    razorpay_order_id = Column(Text, nullable=False, unique=True, index=True)
    razorpay_payment_id = Column(Text, nullable=True, index=True)
    razorpay_signature = Column(Text, nullable=True)
    
    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(Text, server_default=text("'INR'"))
    status = Column(Text, server_default=text("'created'"), index=True)  # created, paid, failed, refunded
    payment_method = Column(Text, nullable=True)  # card, netbanking, upi, wallet
    
    # Metadata
    failure_reason = Column(Text, nullable=True)
    refund_amount = Column(Numeric(10, 2), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    updated_at = Column(DateTime(timezone=True), server_default=text('now()'))
    
    # Relationships
    booking = relationship('Booking', backref='payments')
    user = relationship('User', backref='payments')