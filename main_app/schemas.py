from pydantic import BaseModel, Field, validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime
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
    owner_id: str
    brand: str
    model: str
    latitude: float
    longitude: float
    available: bool

class VehiclePhoto(BaseModel):
    id: UUID
    photo_url: str
    is_primary: bool
    
    class Config:
        from_attributes = True

class VehicleResponse(BaseModel):
    id: UUID
    owner_id: UUID
    brand: str
    model: str
    latitude: float
    longitude: float
    available: bool
    created_at: datetime
    photos: List[VehiclePhoto] = []
    
    class Config:
        from_attributes = True