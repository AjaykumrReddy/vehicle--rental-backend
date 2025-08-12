from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from datetime import datetime, timezone
from .db import Base

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
    
