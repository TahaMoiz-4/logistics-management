"""src/api/v1/vehicles.py — full CRUD for vehicles, company-scoped."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models import Vehicle, Driver, Depot
from src.db.repositories.vehicle import VehicleRepository
from src.api.v1.deps import get_current_user, CurrentUser
from src.exceptions.common import EntityNotFound, ValidationFailed
from src.core.enums import VehicleType, FuelType
from src.schemas.vehicle import VehicleOut, VehicleCreate, VehicleUpdate

router = APIRouter(prefix="/v1/vehicles", tags=["vehicles"])


def _coerce_enums(data: dict) -> dict:
    if data.get("type") is not None:
        try:
            data["type"] = VehicleType(data["type"])
        except ValueError:
            raise ValidationFailed(f"invalid vehicle type '{data['type']}'")
    if data.get("fuel_type") is not None:
        try:
            data["fuel_type"] = FuelType(data["fuel_type"])
        except ValueError:
            raise ValidationFailed(f"invalid fuel type '{data['fuel_type']}'")
    return data


def _to_out(db: Session, v: Vehicle) -> VehicleOut:
    depot = db.query(Depot).filter(Depot.id == v.depot_id).first()
    driver = db.query(Driver).filter(Driver.vehicle_id == v.id, Driver.deleted_at.is_(None)).first()
    return VehicleOut(
        id=v.id, company_id=v.company_id, depot_id=v.depot_id,
        depot_name=depot.name if depot else None,
        license_plate=v.license_plate, type=v.type.value if v.type else None,
        model=v.model, color=v.color, engine_cc=v.engine_cc,
        max_weight_kg=float(v.max_weight_kg) if v.max_weight_kg is not None else None,
        max_volume_m3=float(v.max_volume_m3) if v.max_volume_m3 is not None else None,
        seating_capacity=v.seating_capacity,
        avg_speed_kmh=float(v.avg_speed_kmh) if v.avg_speed_kmh is not None else None,
        fuel_type=v.fuel_type.value if v.fuel_type else None,
        fuel_average=float(v.fuel_average) if v.fuel_average is not None else None,
        monthly_maintenance_cost=float(v.monthly_maintenance_cost) if v.monthly_maintenance_cost is not None else None,
        operational_status=v.operational_status.value if v.operational_status else None,
        assigned_driver_id=driver.id if driver else None,
    )


@router.get("", response_model=list[VehicleOut])
def list_vehicles(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_to_out(db, v) for v in VehicleRepository(db).list(current.company_id)]


@router.get("/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(vehicle_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    v = VehicleRepository(db).get(vehicle_id, current.company_id)
    if v is None:
        raise EntityNotFound("vehicle", vehicle_id)
    return _to_out(db, v)


@router.post("", response_model=VehicleOut, status_code=201)
def create_vehicle(body: VehicleCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    # validate depot belongs to company
    depot = db.query(Depot).filter(Depot.id == body.depot_id, Depot.company_id == current.company_id).first()
    if depot is None:
        raise ValidationFailed(f"depot {body.depot_id} not found for this company")
    data = _coerce_enums(body.model_dump(exclude_unset=True))
    v = VehicleRepository(db).create(data, current.user_id, current.company_id)
    return _to_out(db, v)


@router.put("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: int, body: VehicleUpdate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = VehicleRepository(db)
    v = repo.get(vehicle_id, current.company_id)
    if v is None:
        raise EntityNotFound("vehicle", vehicle_id)
    data = _coerce_enums(body.model_dump(exclude_unset=True))
    v = repo.update(v, data, current.user_id)
    return _to_out(db, v)


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(vehicle_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = VehicleRepository(db)
    v = repo.get(vehicle_id, current.company_id)
    if v is None:
        raise EntityNotFound("vehicle", vehicle_id)
    repo.soft_delete(v, current.user_id)
