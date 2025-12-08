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
from ..logging_config import get_logger, log_error
from ..sms_service import sms_service

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user with phone number"""
    logger.info(f"User registration attempt", extra={"phone_number": user_data.phone_number, "email": user_data.email})
    
    try:
        db_user = User(
            phone_number=user_data.phone_number,
            full_name=user_data.full_name,
            email=user_data.email
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"User registered successfully", extra={"user_id": str(db_user.id), "phone_number": user_data.phone_number})
        return db_user
    
    except IntegrityError as e:
        db.rollback()
        if "phone_number" in str(e.orig):
            logger.warning(f"Registration failed - phone number already exists", extra={"phone_number": user_data.phone_number})
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already registered"
            )
        elif "email" in str(e.orig):
            logger.warning(f"Registration failed - email already exists", extra={"email": user_data.email})
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
        log_error(logger, e, {"phone_number": user_data.phone_number, "email": user_data.email}, "user_registration_error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed"
        )
    
    except Exception as e:
        db.rollback()
        log_error(logger, e, {"phone_number": user_data.phone_number}, "user_registration_unexpected_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to server error"
        )

@router.post("/send-otp", response_model=OTPResponse)
def send_otp(otp_data: SendOTP, db: Session = Depends(get_db)):
    """Send OTP to phone number"""
    logger.info(f"OTP request", extra={"phone_number": otp_data.phone_number})
    
    try:
        user = db.query(User).filter(User.phone_number == otp_data.phone_number).first()
        
        if not user:
            logger.warning(f"OTP request for unregistered phone number", extra={"phone_number": otp_data.phone_number})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phone number not registered"
            )
        
        if not user.is_active:
            logger.warning(f"OTP request for deactivated account", extra={"phone_number": otp_data.phone_number, "user_id": str(user.id)})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated"
            )
        
        otp_code = generate_otp()
        otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
        
        user.otp_code = otp_code
        user.otp_expires_at = otp_expires_at
        db.commit()
        
        logger.info(f"OTP generated successfully", extra={"phone_number": otp_data.phone_number, "user_id": str(user.id)})
        
        # TODO: Send OTP via SMS service (Twilio, AWS SNS, etc.)
        print(f"OTP for {otp_data.phone_number}: {otp_code}")  # Remove in production
        # sms_sent = sms_service.send_otp(otp_data.phone_number, otp_code)
        # if not sms_sent:
        #     logger.error(f"Failed to send OTP SMS", extra={"phone_number": otp_data.phone_number, "user_id": str(user.id)})
        #     raise HTTPException(
        #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        #         detail="Failed to send OTP. Please try again."
        #     )
        
        return {
            "message": "OTP sent successfully",
            "expires_in": OTP_EXPIRE_MINUTES * 60
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, e, {"phone_number": otp_data.phone_number}, "send_otp_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP"
        )

@router.post("/verify-otp", response_model=Token)
def verify_otp(otp_data: VerifyOTP, db: Session = Depends(get_db)):
    """Verify OTP and return long-lived JWT token"""
    logger.info(f"OTP verification attempt", extra={"phone_number": otp_data.phone_number})
    
    try:
        user = db.query(User).filter(User.phone_number == otp_data.phone_number).first()
        
        if not user:
            logger.warning(f"OTP verification failed - phone number not registered", extra={"phone_number": otp_data.phone_number})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phone number not registered"
            )
        
        if not user.otp_code or not user.otp_expires_at:
            logger.warning(f"OTP verification failed - no OTP request found", extra={"phone_number": otp_data.phone_number, "user_id": str(user.id)})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No OTP request found. Please request OTP first"
            )
        
        if not is_otp_valid(user.otp_expires_at):
            logger.warning(f"OTP verification failed - expired OTP", extra={"phone_number": otp_data.phone_number, "user_id": str(user.id)})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired. Please request a new one"
            )
        
        if user.otp_code != otp_data.otp_code:
            logger.warning(f"OTP verification failed - invalid OTP", extra={"phone_number": otp_data.phone_number, "user_id": str(user.id), "provided_otp": otp_data.otp_code})
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
        
        logger.info(f"User authenticated successfully", extra={"phone_number": otp_data.phone_number, "user_id": str(user.id)})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            "user": user
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, e, {"phone_number": otp_data.phone_number}, "verify_otp_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OTP verification failed"
        )

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
        VehicleModel.deleted_at.is_(None),
        VehicleModel.available.is_(True)
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