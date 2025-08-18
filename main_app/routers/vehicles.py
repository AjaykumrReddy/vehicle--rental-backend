from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_X, ST_Y
from uuid import UUID
from typing import List
import uuid
from supabase import create_client, Client
import os
from ..db import get_db
from ..models import VehicleModel, VehiclePhoto
from ..schemas import Vehicle, VehicleResponse
from ..auth import get_current_user

# Supabase client with service role key for server operations
supabase_url = os.getenv("SUPABASE_URL")
supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_service_key)

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

@router.post("/register")
def register_vehicle(vehicle: Vehicle, owner_id: str, db: Session = Depends(get_db)):
    """Register a new vehicle"""
    point_wkt = WKTElement(f'POINT({vehicle.longitude} {vehicle.latitude})', srid=4326)
    db_vehicle = VehicleModel(
        owner_id=owner_id,
        brand=vehicle.brand,
        model=vehicle.model,
        location=point_wkt,
        available=vehicle.available,
        vehicle_type=vehicle.vehicle_type,
        color=vehicle.color,
        license_plate=vehicle.license_plate,
        year=vehicle.year
    )
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return {"status": "success", "vehicle_id": str(db_vehicle.id)}

@router.get("/nearby")
def get_nearby_vehicles(lat: float, lng: float, radius_km: float = 5, db: Session = Depends(get_db)):
    """Get vehicles within specified radius ordered by distance"""
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

@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle_details(vehicle_id: str, db: Session = Depends(get_db)):
    """Get full vehicle information by ID"""
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

@router.post("/{vehicle_id}/photos")
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