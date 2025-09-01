from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
from datetime import datetime, timezone
from ..db import get_db
from ..models import Booking, VehicleModel, VehiclePricing
from ..auth import get_current_user

router = APIRouter(prefix="/owner", tags=["owner"])

@router.put("/bookings/{booking_id}/status")
def update_booking_status(
    booking_id: str,
    status_data: dict,
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update booking status (CONFIRMED/REJECTED)"""
    try:
        booking_uuid = UUID(booking_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    new_status = status_data.get("status")
    if new_status not in ["CONFIRMED", "REJECTED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be CONFIRMED or REJECTED"
        )
    
    booking = db.query(Booking).join(VehicleModel).filter(
        Booking.id == booking_uuid,
        VehicleModel.owner_id == current_user_data["user_id"],
        Booking.status == 'pending'
    ).first()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or cannot be updated"
        )
    
    if new_status == "CONFIRMED":
        booking.status = 'confirmed'
        booking.confirmed_at = datetime.now(timezone.utc)
        message = "Booking confirmed successfully"
    else:  # REJECTED
        booking.status = 'cancelled'
        booking.cancelled_at = datetime.now(timezone.utc)
        booking.cancellation_reason = "Rejected by owner"
        message = "Booking rejected successfully"
    
    db.commit()
    return {"message": message, "status": new_status}

@router.put("/vehicles/{vehicle_id}/availability")
def update_vehicle_availability(
    vehicle_id: str,
    availability_data: dict,
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update vehicle availability"""
    try:
        vehicle_uuid = UUID(vehicle_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vehicle ID format"
        )
    
    is_available = availability_data.get("is_available")
    if not isinstance(is_available, bool):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="is_available must be a boolean"
        )
    
    vehicle = db.query(VehicleModel).filter(
        VehicleModel.id == vehicle_uuid,
        VehicleModel.owner_id == current_user_data["user_id"],
        VehicleModel.deleted_at.is_(None)
    ).first()
    
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )
    
    vehicle.available = is_available
    db.commit()
    
    return {
        "message": f"Vehicle {'activated' if is_available else 'deactivated'} successfully",
        "is_available": is_available
    }

@router.put("/vehicles/{vehicle_id}/rates")
def update_vehicle_rates(
    vehicle_id: str,
    rates_data: dict,
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update vehicle hourly and daily rates"""
    try:
        vehicle_uuid = UUID(vehicle_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vehicle ID format"
        )
    
    hourly_rate = rates_data.get("hourly_rate")
    daily_rate = rates_data.get("daily_rate")
    
    if hourly_rate is not None and (not isinstance(hourly_rate, (int, float)) or hourly_rate <= 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="hourly_rate must be a positive number"
        )
    
    if daily_rate is not None and (not isinstance(daily_rate, (int, float)) or daily_rate <= 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="daily_rate must be a positive number"
        )
    
    vehicle = db.query(VehicleModel).filter(
        VehicleModel.id == vehicle_uuid,
        VehicleModel.owner_id == current_user_data["user_id"],
        VehicleModel.deleted_at.is_(None)
    ).first()
    
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )
    
    # Update or create pricing
    pricing = db.query(VehiclePricing).filter(
        VehiclePricing.vehicle_id == vehicle_uuid
    ).first()
    
    if pricing:
        if hourly_rate is not None:
            pricing.base_hourly_rate = hourly_rate
        if daily_rate is not None:
            pricing.daily_rate = daily_rate
        pricing.updated_at = datetime.now(timezone.utc)
    else:
        pricing = VehiclePricing(
            vehicle_id=vehicle_uuid,
            base_hourly_rate=hourly_rate or 0,
            daily_rate=daily_rate
        )
        db.add(pricing)
    
    db.commit()
    
    return {
        "message": "Vehicle rates updated successfully",
        "hourly_rate": float(pricing.base_hourly_rate),
        "daily_rate": float(pricing.daily_rate) if pricing.daily_rate else None
    }