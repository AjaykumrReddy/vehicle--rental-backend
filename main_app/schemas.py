from pydantic import BaseModel, Field, validator
from typing import Optional
from uuid import UUID
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