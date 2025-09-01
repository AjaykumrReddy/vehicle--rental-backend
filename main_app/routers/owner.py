from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from ..db import get_db
from ..models import VehicleModel, Booking, VehicleAvailabilitySlot, VehiclePhoto
from ..schemas import OwnerDashboardStats, OwnerBookingResponse, BookingActionRequest
from ..auth import get_current_user

router = APIRouter(prefix="/owner", tags=["owner"])

@router.patch("/bookings/{booking_id}/approve")
def approve_booking(
    booking_id: str,
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Approve a pending booking"""
    try:
        booking_uuid = UUID(booking_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    # Check if booking belongs to owner's vehicle
    booking = db.query(Booking).join(VehicleModel).filter(
        Booking.id == booking_uuid,
        VehicleModel.owner_id == current_user_data["user_id"],
        Booking.status == 'pending'
    ).first()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or cannot be approved"
        )
    
    booking.status = 'confirmed'
    booking.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    
    return {"message": "Booking approved successfully"}

@router.patch("/bookings/{booking_id}/reject")
def reject_booking(
    booking_id: str,
    reason: str = Query(..., min_length=1, max_length=500),
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reject a pending booking"""
    try:
        booking_uuid = UUID(booking_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    booking = db.query(Booking).join(VehicleModel).filter(
        Booking.id == booking_uuid,
        VehicleModel.owner_id == current_user_data["user_id"],
        Booking.status == 'pending'
    ).first()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or cannot be rejected"
        )
    
    booking.status = 'cancelled'
    booking.cancelled_at = datetime.now(timezone.utc)
    booking.cancellation_reason = f"Rejected by owner: {reason}"
    db.commit()
    
    return {"message": "Booking rejected successfully"}

@router.get("/bookings/pending")
def get_pending_bookings(
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all pending bookings for owner's vehicles"""
    owner_id = current_user_data["user_id"]
    
    bookings_sql = """
        SELECT 
            b.id, b.start_time, b.end_time, b.total_amount, b.created_at,
            b.pickup_address, b.special_instructions,
            v.vehicle_type, v.brand, v.model, v.license_plate,
            u.full_name as renter_name, u.phone_number as renter_phone
        FROM bookings b
        JOIN vehicles v ON b.vehicle_id = v.id
        JOIN users u ON b.renter_id = u.id
        WHERE v.owner_id = :owner_id AND b.status = 'pending'
        ORDER BY b.created_at ASC
    """
    
    bookings = db.execute(text(bookings_sql), {"owner_id": owner_id}).fetchall()
    
    return [
        {
            "booking_id": str(booking.id),
            "vehicle" : {
                "vehicle_type": booking.vehicle_type,
                "brand": booking.brand,
                "model": booking.model,
                "license_plate": booking.license_plate
            },
            "customer":{
                "name": booking.renter_name,
                "phone": booking.renter_phone
            },
            "start_time": booking.start_time.isoformat(),
            "end_time": booking.end_time.isoformat(),
            "total_amount": float(booking.total_amount),
            "pickup_address": booking.pickup_address,
            "special_instructions": booking.special_instructions,
            "created_at": booking.created_at.isoformat()
        }
        for booking in bookings
    ]

@router.get("/bookings/active")
def get_active_bookings(
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all active/confirmed bookings for owner's vehicles"""
    owner_id = current_user_data["user_id"]
    
    bookings_sql = """
        SELECT 
            b.id, b.start_time, b.end_time, b.status, b.total_amount, b.created_at,
            b.pickup_address, b.dropoff_address,
            v.vehicle_type, v.brand, v.model, v.license_plate,
            u.full_name as renter_name, u.phone_number as renter_phone
        FROM bookings b
        JOIN vehicles v ON b.vehicle_id = v.id
        JOIN users u ON b.renter_id = u.id
        WHERE v.owner_id = :owner_id AND b.status IN ('confirmed', 'active')
        ORDER BY b.start_time ASC
    """
    
    bookings = db.execute(text(bookings_sql), {"owner_id": owner_id}).fetchall()
    
    return [
        {
            "id": str(booking.id),
            "vehicle" : {
                "vehicle_type": booking.vehicle_type,
                "brand": booking.brand,
                "model": booking.model,
                "license_plate": booking.license_plate
            },
            "customer":{
                "name": booking.renter_name,
                "phone": booking.renter_phone
            },
            "start_time": booking.start_time.isoformat(),
            "end_time": booking.end_time.isoformat(),
            "status": booking.status.upper(),
            "total_amount": float(booking.total_amount),
            "pickup_address": booking.pickup_address,
            "dropoff_address": booking.dropoff_address,
            "created_at": booking.created_at.isoformat()
        }
        for booking in bookings
    ]

@router.get("/vehicles")
def get_owner_vehicles(
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all vehicles owned by current user with booking stats"""
    owner_id = current_user_data["user_id"]
    
    vehicles_sql = """
        SELECT 
            v.id, v.brand, v.model, v.vehicle_type, v.color, v.year, 
            v.license_plate, v.available, v.created_at,
            COUNT(b.id) as total_bookings,
            COUNT(CASE WHEN b.status = 'pending' THEN 1 END) as pending_bookings,
            COUNT(CASE WHEN b.status IN ('confirmed', 'active') THEN 1 END) as active_bookings,
            COALESCE(SUM(CASE WHEN b.status IN ('confirmed', 'completed') THEN b.total_amount END), 0) as total_earnings
        FROM vehicles v
        LEFT JOIN bookings b ON v.id = b.vehicle_id
        WHERE v.owner_id = :owner_id AND v.deleted_at IS NULL
        GROUP BY v.id
        ORDER BY v.created_at DESC
    """
    
    vehicles = db.execute(text(vehicles_sql), {"owner_id": owner_id}).fetchall()
    
    return {
        "vehicles": [
            {
                "id": str(vehicle.id),
                "name": f"{vehicle.brand} {vehicle.model}",
                "vehicle_type": vehicle.vehicle_type,
                "color": vehicle.color,
                "year": vehicle.year,
                "license_plate": vehicle.license_plate,
                "available": vehicle.available,
                "stats": {
                    "total_bookings": vehicle.total_bookings,
                    "pending_bookings": vehicle.pending_bookings,
                    "active_bookings": vehicle.active_bookings,
                    "total_earnings": float(vehicle.total_earnings)
                },
                "created_at": vehicle.created_at.isoformat()
            }
            for vehicle in vehicles
        ]
    }

@router.patch("/vehicles/{vehicle_id}/toggle-availability")
def toggle_vehicle_availability(
    vehicle_id: str,
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle vehicle availability"""
    try:
        vehicle_uuid = UUID(vehicle_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vehicle ID format"
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
    
    vehicle.available = not vehicle.available
    db.commit()
    
    return {
        "message": f"Vehicle {'activated' if vehicle.available else 'deactivated'} successfully",
        "available": vehicle.available
    }

@router.get("/earnings")
def get_earnings_summary(
    current_user_data: dict = Depends(get_current_user),
    period: str = Query("month", regex="^(week|month|year)$"),
    db: Session = Depends(get_db)
):
    """Get earnings summary for different periods"""
    owner_id = current_user_data["user_id"]
    
    # Calculate date range based on period
    now = datetime.now(timezone.utc)
    if period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:  # year
        start_date = now - timedelta(days=365)
    
    earnings_sql = """
        SELECT 
            DATE(b.created_at) as date,
            COUNT(b.id) as bookings_count,
            SUM(b.total_amount) as daily_earnings
        FROM bookings b
        JOIN vehicles v ON b.vehicle_id = v.id
        WHERE v.owner_id = :owner_id 
        AND b.status IN ('confirmed', 'completed')
        AND b.created_at >= :start_date
        GROUP BY DATE(b.created_at)
        ORDER BY date DESC
    """
    
    earnings = db.execute(text(earnings_sql), {
        "owner_id": owner_id,
        "start_date": start_date
    }).fetchall()
    
    total_earnings = sum(float(e.daily_earnings) for e in earnings)
    total_bookings = sum(e.bookings_count for e in earnings)
    
    return {
        "period": period,
        "total_earnings": total_earnings,
        "total_bookings": total_bookings,
        "daily_breakdown": [
            {
                "date": earning.date.isoformat(),
                "bookings": earning.bookings_count,
                "earnings": float(earning.daily_earnings)
            }
            for earning in earnings
        ]
    }