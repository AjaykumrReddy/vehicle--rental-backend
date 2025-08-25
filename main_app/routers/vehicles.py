from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_X, ST_Y
from uuid import UUID
from typing import List
from datetime import datetime, time
import uuid
from supabase import create_client, Client
import os
from ..db import get_db
from ..models import VehicleModel, VehiclePhoto, VehiclePricing, VehicleAvailabilitySlot, Booking
from ..schemas import Vehicle, VehicleResponse, SetAvailabilityRequest, AvailabilitySlotResponse
from ..auth import get_current_user

# Supabase client with service role key for server operations
supabase_url = os.getenv("SUPABASE_URL")
supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_service_key)

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

@router.post("/register")
def register_vehicle(vehicle: Vehicle, owner_id: str, db: Session = Depends(get_db)):
    """Register a new vehicle with user-friendly error messages"""
    try:
        point_wkt = WKTElement(f'POINT({vehicle.longitude} {vehicle.latitude})', srid=4326)
        db_vehicle = VehicleModel(
            owner_id=owner_id,
            brand=vehicle.brand,
            model=vehicle.model,
            location=point_wkt,
            available=vehicle.available,
            vehicle_type=vehicle.vehicle_type,
            color=vehicle.color,
            license_plate=vehicle.license_plate.upper(),
            year=vehicle.year
        )
        db.add(db_vehicle)
        db.commit()
        db.refresh(db_vehicle)
        return {"status": "success", "vehicle_id": str(db_vehicle.id)}
    
    except IntegrityError as e:
        db.rollback()
        if "license_plate" in str(e.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This license plate is already registered. Please check and enter the correct license plate."
            )
        elif "owner_id" in str(e.orig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your session has expired. Please log in again to register your vehicle."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vehicle information conflicts with existing data. Please check your details."
        )
    
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to connect to server. Please check your internet connection and try again."
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/nearby")
def get_nearby_vehicles(lat: float, lng: float, radius_km: float = 5, db: Session = Depends(get_db)):
    """Get vehicles within specified radius ordered by distance"""
    try:
        # Validate coordinates
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid coordinates"
            )
        
        if radius_km <= 0 or radius_km > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Radius must be between 0 and 100 km"
            )
        
        point_wkt = f'SRID=4326;POINT({lng} {lat})'
        sql = """
            SELECT id, owner_id, vehicle_type, brand, model, ST_AsText(location::geometry) as location,
            color, year, available, created_at,
            ROUND(ST_Distance(location::geography, ST_GeogFromText(:point))::numeric, 0) as distance_meters
            FROM vehicles
            WHERE ST_DWithin(location::geography, ST_GeogFromText(:point), :radius)
            AND available = true
            AND deleted_at IS NULL
            ORDER BY ST_Distance(location::geography, ST_GeogFromText(:point))
        """
        result = db.execute(text(sql), {"point": point_wkt, "radius": radius_km * 1000})
        return result.mappings().all()
    
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle_details(vehicle_id: str, db: Session = Depends(get_db)):
    """Get full vehicle information by ID"""
    try:
        # Validate UUID format
        try:
            uuid_obj = UUID(vehicle_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid vehicle ID format"
            )
        
        vehicle = db.query(VehicleModel).filter(
            VehicleModel.id == uuid_obj,
            VehicleModel.deleted_at.is_(None)
        ).first()
        
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found"
            )
        
        # Get coordinates from PostGIS geometry
        lat = db.scalar(ST_Y(vehicle.location))
        lng = db.scalar(ST_X(vehicle.location))
        
        # Get vehicle photos
        photos = db.query(VehiclePhoto).filter(VehiclePhoto.vehicle_id == vehicle_id).all()
        
        return {
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
            "photos": photos
        }
    
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@router.post("/{vehicle_id}/upload_photos")
def upload_vehicle_photos(
    vehicle_id: str,
    files: List[UploadFile] = File(...),
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload photos for a vehicle"""
    try:
        uuid_obj = UUID(vehicle_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vehicle ID format"
        )
    
    vehicle = db.query(VehicleModel).filter(
        VehicleModel.id == uuid_obj,
        VehicleModel.owner_id == current_user_data["user_id"]
    ).first()
    
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )
    
    uploaded_photos = []
    
    for i, file in enumerate(files):
        # Validate file type
        if file.content_type not in ["image/jpeg", "image/png", "image/jpg"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only JPEG/PNG files allowed"
            )
        
        # Generate unique filename
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"vehicles/{vehicle_id}/{uuid.uuid4()}.{file_extension}"
        
        # Upload to Supabase Storage
        try:
            file_content = file.file.read()
            result = supabase.storage.from_("vehicle-photos").upload(
                unique_filename, 
                file_content,
                {"content-type": file.content_type}
            )
            
            # Get public URL
            public_url = supabase.storage.from_("vehicle-photos").get_public_url(unique_filename)
            
            # Save to database
            db_photo = VehiclePhoto(
                vehicle_id=uuid_obj,
                photo_url=public_url,
                is_primary=(i == 0)
            )
            db.add(db_photo)
            uploaded_photos.append({"url": public_url, "is_primary": (i == 0)})
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload photo: {str(e)}"
            )
    
    db.commit()
    return {"message": f"Uploaded {len(files)} photos", "photos": uploaded_photos}

@router.post("/{vehicle_id}/availability_slots")
def set_vehicle_availability(
    vehicle_id: str,
    availability_data: SetAvailabilityRequest,
    current_user_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set vehicle availability slots"""
    try:
        uuid_obj = UUID(vehicle_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vehicle ID format"
        )
    
    vehicle = db.query(VehicleModel).filter(
        VehicleModel.id == uuid_obj,
        VehicleModel.owner_id == current_user_data["user_id"]
    ).first()
    
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )
    
    # # Only delete future slots (preserve slots with bookings)
    # current_time = datetime.utcnow()
    
    # # Get slots with active bookings
    # slots_with_bookings = db.query(VehicleAvailabilitySlot.id).filter(
    #     VehicleAvailabilitySlot.vehicle_id == uuid_obj,
    #     VehicleAvailabilitySlot.start_datetime > current_time
    # ).join(Booking, 
    #     (Booking.vehicle_id == VehicleAvailabilitySlot.vehicle_id) &
    #     (Booking.start_time >= VehicleAvailabilitySlot.start_datetime) &
    #     (Booking.end_time <= VehicleAvailabilitySlot.end_datetime) &
    #     (Booking.status.in_(['confirmed', 'active']))
    # ).subquery()
    
    # # Delete only future slots without bookings
    # db.query(VehicleAvailabilitySlot).filter(
    #     VehicleAvailabilitySlot.vehicle_id == uuid_obj,
    #     VehicleAvailabilitySlot.start_datetime > current_time,
    #     ~VehicleAvailabilitySlot.id.in_(slots_with_bookings)
    # ).delete(synchronize_session=False)
    
    # Create new slots
    for slot in availability_data.slots:
        db_slot = VehicleAvailabilitySlot(
            vehicle_id=uuid_obj,
            start_datetime=slot.start_datetime,
            end_datetime=slot.end_datetime,
            hourly_rate=slot.hourly_rate,
            daily_rate=slot.daily_rate,
            weekly_rate=slot.weekly_rate,
            min_rental_hours=slot.min_rental_hours,
            max_rental_hours=slot.max_rental_hours
        )
        db.add(db_slot)
    
    db.commit()
    return {"message": f"Set {len(availability_data.slots)} availability slots"}


@router.get("/{vehicle_id}/availability_slots", response_model=List[AvailabilitySlotResponse])
def get_vehicle_availability(vehicle_id: str, db: Session = Depends(get_db)):
    """Get vehicle availability slots"""
    try:
        uuid_obj = UUID(vehicle_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vehicle ID format"
        )
    
    slots = db.query(VehicleAvailabilitySlot).filter(
        VehicleAvailabilitySlot.vehicle_id == uuid_obj,
        VehicleAvailabilitySlot.is_active == True
    ).order_by(VehicleAvailabilitySlot.start_datetime).all()
    
    return slots

@router.delete("/{vehicle_id}")
def delete_vehicle(vehicle_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a vehicle (soft delete)"""
    try:
        uuid_obj = UUID(vehicle_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vehicle ID format"
        )
    
    try:
        # Verify vehicle ownership
        vehicle = db.query(VehicleModel).filter(
            VehicleModel.id == uuid_obj,
            VehicleModel.owner_id == current_user["user_id"],
            VehicleModel.deleted_at.is_(None)
        ).first()
        print("Vehicle found:", vehicle)
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found or you don't have permission to delete it"
            )
        
        # # Check for active bookings
        # active_bookings = db.query(Booking).filter(
        #     Booking.vehicle_id == uuid_obj,
        #     Booking.status.in_(['confirmed', 'active']),
        #     Booking.end_time > datetime.utcnow()
        # ).count()
        
        # if active_bookings > 0:
        #     raise HTTPException(
        #         status_code=status.HTTP_409_CONFLICT,
        #         detail="Cannot delete vehicle with active or upcoming bookings"
        #     )
        
        # Soft delete - set deleted_at timestamp
        vehicle.deleted_at = datetime.utcnow()
        vehicle.available = False
        
        # Deactivate availability slots
        db.query(VehicleAvailabilitySlot).filter(
            VehicleAvailabilitySlot.vehicle_id == uuid_obj
        ).update({"is_active": False})
        
        db.commit()
        return {
            "status": "success",
            "message": "Vehicle deleted successfully",
            "vehicle_id": str(vehicle_id)
        }
    
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete vehicle due to data constraints"
        )
    
    except SQLAlchemyError as e:
        print(e)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while deleting vehicle"
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        print(e)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )
