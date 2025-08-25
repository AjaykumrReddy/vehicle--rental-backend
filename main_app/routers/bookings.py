from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from datetime import datetime, timezone
from typing import List
from ..db import get_db
from ..models import Booking, VehicleModel, VehicleAvailabilitySlot
from ..schemas import BookingRequest, BookingResponse
from ..auth import get_current_user

router = APIRouter(prefix="/bookings", tags=["bookings"])

@router.post("/", response_model=BookingResponse)
def create_booking(
    booking_data: BookingRequest,
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new booking"""
    try:
        vehicle_uuid = UUID(booking_data.vehicle_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vehicle ID format"
        )
    
    # Check vehicle exists and is available
    vehicle = db.query(VehicleModel).filter(
        VehicleModel.id == vehicle_uuid,
        VehicleModel.available == True,
        VehicleModel.deleted_at.is_(None)
    ).first()
    
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found or not available"
        )
    
    # Check for conflicting bookings
    conflicting_booking = db.query(Booking).filter(
        Booking.vehicle_id == vehicle_uuid,
        Booking.status.in_(['confirmed', 'active']),
        Booking.start_time < booking_data.end_time,
        Booking.end_time > booking_data.start_time
    ).first()
    
    if conflicting_booking:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehicle is already booked for this time period"
        )
    
    # Validate availability slot if provided
    availability_slot_uuid = None
    if booking_data.availability_slot_id:
        try:
            availability_slot_uuid = UUID(booking_data.availability_slot_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid availability slot ID format"
            )
        
        # Check if slot exists and is active
        slot = db.query(VehicleAvailabilitySlot).filter(
            VehicleAvailabilitySlot.id == availability_slot_uuid,
            VehicleAvailabilitySlot.vehicle_id == vehicle_uuid,
            VehicleAvailabilitySlot.is_active == True
        ).first()
        
        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability slot not found or inactive"
            )
        
        # Validate booking time is within slot time
        if (booking_data.start_time < slot.start_datetime or 
            booking_data.end_time > slot.end_datetime):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking time must be within availability slot time"
            )
    
    # Create booking
    booking = Booking(
        vehicle_id=vehicle_uuid,
        renter_id=current_user_data["user_id"],
        availability_slot_id=availability_slot_uuid,
        start_time=booking_data.start_time,
        end_time=booking_data.end_time,
        base_amount=booking_data.base_amount,
        security_deposit=booking_data.security_deposit,
        platform_fee=booking_data.platform_fee,
        total_amount=booking_data.total_amount,
        pickup_address=booking_data.pickup_address,
        dropoff_address=booking_data.dropoff_address,
        special_instructions=booking_data.special_instructions
    )
    
    db.add(booking)
    db.commit()
    db.refresh(booking)
    
    return booking

@router.get("/", response_model=List[BookingResponse])
def get_user_bookings(
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all bookings for current user"""
    bookings = db.query(Booking).filter(
        Booking.renter_id == current_user_data["user_id"]
    ).order_by(Booking.created_at.desc()).all()
    
    return bookings

@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: str,
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific booking details"""
    try:
        booking_uuid = UUID(booking_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    booking = db.query(Booking).filter(
        Booking.id == booking_uuid,
        Booking.renter_id == current_user_data["user_id"]
    ).first()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return booking

@router.patch("/{booking_id}/cancel")
def cancel_booking(
    booking_id: str,
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a booking"""
    try:
        booking_uuid = UUID(booking_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    booking = db.query(Booking).filter(
        Booking.id == booking_uuid,
        Booking.renter_id == current_user_data["user_id"]
    ).first()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    if booking.status in ['completed', 'cancelled']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel completed or already cancelled booking"
        )
    
    booking.status = 'cancelled'
    booking.cancelled_at = datetime.now(timezone.utc)
    booking.cancellation_reason = "Cancelled by user"
    
    db.commit()
    
    return {"message": "Booking cancelled successfully"}

@router.patch("/{booking_id}/confirm")
def confirm_booking(
    booking_id: str,
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm a booking (after payment)"""
    try:
        booking_uuid = UUID(booking_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    booking = db.query(Booking).filter(
        Booking.id == booking_uuid,
        Booking.renter_id == current_user_data["user_id"]
    ).first()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    if booking.status != 'pending':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending bookings can be confirmed"
        )
    
    booking.status = 'confirmed'
    booking.confirmed_at = datetime.now(timezone.utc)
    booking.payment_status = 'completed'
    
    db.commit()
    
    return {"message": "Booking confirmed successfully"}