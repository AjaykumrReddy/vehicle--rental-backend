from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from geoalchemy2.elements import WKTElement
from ..db import get_db
from ..models import VehicleModel
from ..schemas import Vehicle

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

@router.post("/register")
def register_vehicle(vehicle: Vehicle, db: Session = Depends(get_db)):
    """Register a new vehicle"""
    point_wkt = WKTElement(f'POINT({vehicle.longitude} {vehicle.latitude})', srid=4326)
    db_vehicle = VehicleModel(
        owner_id=vehicle.owner_id,
        brand=vehicle.brand,
        model=vehicle.model,
        location=point_wkt,
        available=vehicle.available
    )
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return {"status": "success", "vehicle_id": str(db_vehicle.id)}

@router.get("/nearby")
def get_nearby_vehicles(lat: float, lng: float, radius_km: float = 5, db: Session = Depends(get_db)):
    """Get vehicles within specified radius"""
    point_wkt = f'SRID=4326;POINT({lng} {lat})'
    sql = """
        SELECT id, owner_id, brand, model, ST_AsText(location::geometry) as location, available, created_at
        FROM vehicles
        WHERE ST_DWithin(location::geography, ST_GeogFromText(:point), :radius)
        AND available = true
        AND deleted_at IS NULL
    """
    result = db.execute(text(sql), {"point": point_wkt, "radius": radius_km * 1000})
    return result.mappings().all()