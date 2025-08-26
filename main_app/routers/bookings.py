from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
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

@router.get("/")
def get_user_bookings(
    current_user_data: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, le=1000, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str = Query(None, regex="^(pending|confirmed|active|completed|cancelled)$", description="Filter by status"),
    db: Session = Depends(get_db)
):
    """Get user bookings with vehicle details - production optimized"""
    try:
        # Validate user_id format
        try:
            user_uuid = UUID(current_user_data["user_id"])
        except (ValueError, KeyError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user session"
            )
        
        offset = (page - 1) * limit
        
        # Build dynamic WHERE clause
        where_conditions = ["b.renter_id = :user_id"]
        params = {
            "user_id": str(user_uuid),
            "limit": limit + 1,  # Get one extra to check has_more
            "offset": offset
        }
        
        if status_filter:
            where_conditions.append("b.status = :status")
            params["status"] = status_filter
        
        where_clause = " AND ".join(where_conditions)
        
        # Optimized query with only essential fields
        sql = f"""
            SELECT 
                b.id, b.vehicle_id, b.start_time, b.end_time, 
                b.status, b.total_amount, b.created_at,
                v.brand, v.model, v.vehicle_type, v.color, v.year
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            WHERE {where_clause}
            ORDER BY b.created_at DESC
            LIMIT :limit OFFSET :offset
        """
        
        result = db.execute(text(sql), params).fetchall()
        
        # Check if there are more records
        has_more = len(result) > limit
        records = result[:limit] if has_more else result
        
        # Fast response formatting
        bookings = []
        for row in records:
            try:
                booking = {
                    "id": str(row.id),
                    "vehicle_id": str(row.vehicle_id),
                    "start_time": row.start_time.isoformat() if row.start_time else None,
                    "end_time": row.end_time.isoformat() if row.end_time else None,
                    "status": row.status.upper() if row.status else "UNKNOWN",
                    "total_amount": float(row.total_amount) if row.total_amount else 0.0,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "vehicle": {
                        "brand": row.brand or "Unknown",
                        "model": row.model or "Unknown",
                        "vehicle_type": row.vehicle_type or "Unknown",
                        "color": row.color or "Unknown",
                        "year": row.year or 0
                    }
                }
                bookings.append(booking)
            except (AttributeError, ValueError) as e:
                # Skip malformed records, log in production
                continue
        
        return {
            "success": True,
            "data": {
                "bookings": bookings,
                "page": page,
                "limit": limit,
                "has_more": has_more,
                "total_returned": len(bookings),
                "filters": {
                    "status": status_filter
                }
            }
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        # Log error in production
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch bookings. Please try again."
        )


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