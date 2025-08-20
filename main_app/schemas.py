from pydantic import BaseModel, Field, validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime, time, date
from decimal import Decimal
import re

class UserRegister(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=15)
    full_name: str = Field(..., min_length=2, max_length=100)
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    
    @validator('phone_number')
    def validate_phone(cls, v):
        if not re.match(r'^[+]?[0-9]{10,15}$', v):
            raise ValueError('Invalid phone number format')
        return v

class SendOTP(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=15)

class VerifyOTP(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=15)
    otp_code: str = Field(..., min_length=4, max_length=6)

class OTPResponse(BaseModel):
    message: str
    expires_in: int

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: 'UserResponse'

class UserResponse(BaseModel):
    id: UUID
    phone_number: str
    full_name: str
    email: Optional[str]
    is_verified: bool
    is_active: bool
    
    class Config:
        from_attributes = True

class Vehicle(BaseModel):
    brand: str
    model: str
    latitude: float
    longitude: float
    available: bool = True
    vehicle_type: str
    color: str
    license_plate: str
    year: int

class VehiclePhoto(BaseModel):
    id: UUID
    photo_url: str
    is_primary: bool
    
    class Config:
        from_attributes = True

class SimpleVehicleResponse(BaseModel):
    id: UUID
    owner_id: UUID
    brand: str
    model: str
    latitude: float
    longitude: float
    available: bool
    created_at: datetime
    photos: List[VehiclePhoto] = []

class AvailabilitySlot(BaseModel):
    start_datetime: datetime
    end_datetime: datetime
    hourly_rate: float
    daily_rate: Optional[float] = None
    weekly_rate: Optional[float] = None
    min_rental_hours: int = 1
    max_rental_hours: Optional[int] = None

class AvailabilitySlotResponse(BaseModel):
    id: UUID
    start_datetime: datetime
    end_datetime: datetime
    hourly_rate: float
    daily_rate: Optional[float]
    weekly_rate: Optional[float]
    min_rental_hours: int
    max_rental_hours: Optional[int]
    is_active: bool
    
    class Config:
        from_attributes = True

class SetAvailabilityRequest(BaseModel):
    slots: List[AvailabilitySlot]

class VehicleResponse(BaseModel):
    id: UUID
    owner_id: UUID
    brand: str
    model: str
    latitude: float
    longitude: float
    available: bool
    vehicle_type: str
    color: str
    license_plate: str
    year: int
    created_at: datetime
    photos: List[VehiclePhoto] = []
    
    class Config:
        from_attributes = True