from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Integer, text, Enum, Numeric, Time, Date, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from datetime import datetime, timezone
from .db import Base
import enum
import uuid

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'), index=True)
    phone_number = Column(Text, unique=True, index=True, nullable=False)
    email = Column(Text, unique=True, index=True, nullable=True)
    full_name = Column(Text, nullable=False)
    otp_code = Column(Text, nullable=True)
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    is_verified = Column(Boolean, server_default=text('false'))
    is_active = Column(Boolean, server_default=text('true'))
    profile_image = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    updated_at = Column(DateTime(timezone=True), server_default=text('now()'))
    deleted_at = Column(DateTime(timezone=True), nullable=True)

class VehicleModel(Base):
    __tablename__ = "vehicles"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'), index=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    owner = relationship('User', backref='vehicles')
    brand = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    available = Column(Boolean, server_default=text('true'))
    vehicle_type = Column(Text, nullable=False)
    color = Column(Text, nullable=False)
    license_plate = Column(Text, unique=True, nullable=False)
    year = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    updated_at = Column(DateTime(timezone=True), server_default=text('now()'))
    deleted_at = Column(DateTime(timezone=True), nullable=True)

class VehiclePhoto(Base):
    __tablename__ = "vehicle_photos"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'), index=True)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey('vehicles.id', ondelete='CASCADE'), nullable=False, index=True)
    photo_url = Column(Text, nullable=False)
    is_primary = Column(Boolean, server_default=text('false'))
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    vehicle = relationship('VehicleModel', backref='photo_list')

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'), index=True)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey('vehicles.id'), nullable=False, index=True)
    renter_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    availability_slot_id = Column(UUID(as_uuid=True), ForeignKey('vehicle_availability_slots.id'), nullable=True, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(Text, nullable=False, server_default=text("'pending'"), index=True)
    
    # Pricing breakdown
    base_amount = Column(Numeric(10, 2), nullable=False)
    security_deposit = Column(Numeric(10, 2), nullable=False, server_default=text('0'))
    platform_fee = Column(Numeric(10, 2), nullable=False, server_default=text('0'))
    total_amount = Column(Numeric(10, 2), nullable=False)
    
    # Payment tracking
    payment_status = Column(Text, nullable=False, server_default=text("'pending'"))
    payment_method = Column(Text, nullable=True)
    payment_id = Column(Text, nullable=True)  # External payment gateway ID
    
    # Locations
    pickup_location = Column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    dropoff_location = Column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    pickup_address = Column(Text, nullable=True)
    dropoff_address = Column(Text, nullable=True)
    
    # Additional info
    special_instructions = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    updated_at = Column(DateTime(timezone=True), server_default=text('now()'))
    
    # Relationships
    vehicle = relationship('VehicleModel', backref='bookings')
    renter = relationship('User', backref='rentals')
    availability_slot = relationship('VehicleAvailabilitySlot', backref='bookings')

class VehicleAvailabilitySlot(Base):
    __tablename__ = "vehicle_availability_slots"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'), index=True)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey('vehicles.id', ondelete='CASCADE'), nullable=False, index=True)
    start_datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    end_datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    hourly_rate = Column(Numeric(8, 2), nullable=False)
    daily_rate = Column(Numeric(8, 2), nullable=True)  # Optional daily rate
    weekly_rate = Column(Numeric(8, 2), nullable=True)  # Optional weekly rate
    min_rental_hours = Column(Integer, server_default=text('1'))  # Minimum rental duration
    max_rental_hours = Column(Integer, nullable=True)  # Maximum rental duration
    is_active = Column(Boolean, server_default=text('true'))
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    
    vehicle = relationship('VehicleModel', backref='availability_slots')

class VehiclePricing(Base):
    __tablename__ = "vehicle_pricing"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'), index=True)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey('vehicles.id', ondelete='CASCADE'), nullable=False, index=True)
    base_hourly_rate = Column(Numeric(8, 2), nullable=False)
    daily_rate = Column(Numeric(8, 2), nullable=True)
    weekly_rate = Column(Numeric(8, 2), nullable=True)
    security_deposit = Column(Numeric(8, 2), nullable=False, server_default=text('0'))
    fuel_policy = Column(Text, nullable=True)  # "full_to_full", "pay_per_km", etc.
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    updated_at = Column(DateTime(timezone=True), server_default=text('now()'))
    
    vehicle = relationship('VehicleModel', backref='pricing', uselist=False)

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'), index=True)
    booking_id = Column(UUID(as_uuid=True), ForeignKey('bookings.id'), nullable=False, unique=True, index=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    renter_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    last_message_at = Column(DateTime(timezone=True), server_default=text('now()'), index=True)
    owner_unread_count = Column(Integer, server_default=text('0'))
    renter_unread_count = Column(Integer, server_default=text('0'))
    is_active = Column(Boolean, server_default=text('true'))
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    
    # Relationships
    booking = relationship('Booking', backref='conversation')
    owner = relationship('User', foreign_keys=[owner_id], backref='owned_conversations')
    renter = relationship('User', foreign_keys=[renter_id], backref='renter_conversations')

class Message(Base):
    __tablename__ = "messages"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'), index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    sender_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    message_text = Column(Text, nullable=False)
    message_type = Column(Text, server_default=text("'text'"))  # text, image, location, system
    attachment_url = Column(Text, nullable=True)  # For images/files
    is_read = Column(Boolean, server_default=text('false'), index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text('now()'), index=True)
    
    # Relationships
    conversation = relationship('Conversation', backref='messages')
    sender = relationship('User', backref='sent_messages')

class ErrorAudit(Base):
    __tablename__ = "error_audits"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Error Classification
    error_type = Column(String(50), nullable=False)  # API_ERROR, UI_ERROR, THIRD_PARTY_ERROR
    severity = Column(String(20), nullable=False)    # LOW, MEDIUM, HIGH, CRITICAL
    source = Column(String(50), nullable=False)      # BACKEND, FRONTEND, EXTERNAL
    
    # Context Information
    user_id = Column(UUID(as_uuid=True), nullable=True)
    session_id = Column(String(100), nullable=True)
    request_id = Column(String(100), nullable=True)
    
    # Error Details
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    
    # Request Context
    endpoint = Column(String(200), nullable=True)
    http_method = Column(String(10), nullable=True)
    http_status = Column(Integer, nullable=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    # Additional Context
    context_data = Column(JSON, nullable=True)  # Custom context data
    environment = Column(String(20), default="production")
    
    # Tracking
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(UUID(as_uuid=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_error_type_created', 'error_type', 'created_at'),
        Index('idx_severity_created', 'severity', 'created_at'),
        Index('idx_user_created', 'user_id', 'created_at'),
        Index('idx_endpoint_created', 'endpoint', 'created_at'),
        Index('idx_resolved_created', 'resolved', 'created_at'),
    )
