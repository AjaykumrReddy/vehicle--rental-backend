from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta, timezone
from typing import List
from ..db import get_db
from ..models import User, VehicleModel
from ..schemas import UserRegister, UserResponse, SendOTP, VerifyOTP, Token, OTPResponse, VehicleResponse
from ..auth import generate_otp, is_otp_valid, create_access_token, OTP_EXPIRE_MINUTES, ACCESS_TOKEN_EXPIRE_DAYS, get_current_user
from geoalchemy2.functions import ST_X, ST_Y

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user with phone number"""
    try:
        db_user = User(
            phone_number=user_data.phone_number,
            full_name=user_data.full_name,
            email=user_data.email
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    
    except IntegrityError as e:
        db.rollback()
        if "phone_number" in str(e.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already registered"
            )
        elif "email" in str(e.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed"
        )

@router.post("/send-otp", response_model=OTPResponse)
def send_otp(otp_data: SendOTP, db: Session = Depends(get_db)):
    """Send OTP to phone number"""
    user = db.query(User).filter(User.phone_number == otp_data.phone_number).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not registered"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated"
        )
    
    otp_code = generate_otp()
    otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
    
    user.otp_code = otp_code
    user.otp_expires_at = otp_expires_at
    db.commit()
    
    # TODO: Send OTP via SMS service (Twilio, AWS SNS, etc.)
    print(f"OTP for {otp_data.phone_number}: {otp_code}")  # Remove in production
    
    return {
        "message": "OTP sent successfully",
        "expires_in": OTP_EXPIRE_MINUTES * 60
    }

@router.post("/verify-otp", response_model=Token)
def verify_otp(otp_data: VerifyOTP, db: Session = Depends(get_db)):
    """Verify OTP and return long-lived JWT token"""
    user = db.query(User).filter(User.phone_number == otp_data.phone_number).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not registered"
        )
    
    if not user.otp_code or not user.otp_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP request found. Please request OTP first"
        )
    
    if not is_otp_valid(user.otp_expires_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new one"
        )
    
    if user.otp_code != otp_data.otp_code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP"
        )
    
    # Clear OTP after successful verification
    user.otp_code = None
    user.otp_expires_at = None
    db.commit()
    
    access_token = create_access_token(
        data={"sub": str(user.id), "phone": user.phone_number}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        "user": user
    }

def get_current_user_from_db(current_user_data: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user from database"""
    user = db.query(User).filter(User.id == current_user_data["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    return user

@router.get("/profile", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user_from_db)):
    """Get current user profile (protected endpoint)"""
    return current_user

@router.get("/vehicles", response_model=List[VehicleResponse])
def get_user_vehicles(current_user: User = Depends(get_current_user_from_db), db: Session = Depends(get_db)):
    """Get all vehicles registered by current user"""
    vehicles = db.query(VehicleModel).filter(
        VehicleModel.owner_id == current_user.id,
        VehicleModel.deleted_at.is_(None)
    ).all()
    
    result = []
    for vehicle in vehicles:
        lat = db.scalar(ST_Y(vehicle.location))
        lng = db.scalar(ST_X(vehicle.location))
        
        result.append({
            "id": vehicle.id,
            "owner_id": vehicle.owner_id,
            "brand": vehicle.brand,
            "model": vehicle.model,
            "latitude": lat,
            "longitude": lng,
            "available": vehicle.available,
            "vehicle_type": vehicle.vehicle_type,
            "color": vehicle.color,
            "license_plate": vehicle.license_plate,
            "year": vehicle.year,
            "created_at": vehicle.created_at,
            "photos": vehicle.photo_list
        })
    
    return result

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, db: Session = Depends(get_db)):
    """Get user by ID"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user