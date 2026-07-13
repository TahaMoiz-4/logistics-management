"""src/api/v1/drivers.py — full CRUD for drivers, company-scoped. Joins Employee + Vehicle."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models import Driver, Employee, Vehicle
from src.db.repositories.driver import DriverRepository
from src.db.repositories.employee import EmployeeRepository
from src.api.v1.deps import get_current_user, CurrentUser
from src.exceptions.common import EntityNotFound, ValidationFailed
from src.core.enums import VehicleType
from src.schemas.driver import DriverOut, DriverCreate, DriverUpdate

router = APIRouter(prefix="/v1/drivers", tags=["drivers"])


def _coerce_skills(skills: list[str]):
    out = []
    for s in skills or []:
        try:
            out.append(VehicleType(s))
        except ValueError:
            raise ValidationFailed(f"invalid vehicle type '{s}'")
    return out


def _to_out(d: Driver, emp: Employee, veh: Vehicle) -> DriverOut:
    return DriverOut(
        id=d.id, company_id=d.company_id, employee_id=d.employee_id,
        name=emp.name if emp else None,
        contact_number=emp.contact_number if emp else None,
        contact_email=emp.contact_email if emp else None,
        drivers_license_number=d.drivers_license_number,
        skills=[s.value if hasattr(s, "value") else str(s) for s in (d.skills or [])],
        rating=d.rating, kms_driven=d.kms_driven, orders_completed=d.orders_completed,
        operational_status=(emp.operational_status.value if emp and emp.operational_status else None),
        unavailable_reason=emp.unavailable_reason if emp else None,
        vehicle_id=d.vehicle_id, vehicle_plate=veh.license_plate if veh else None,
    )


@router.get("", response_model=list[DriverOut])
def list_drivers(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_to_out(d, e, v) for d, e, v in DriverRepository(db).list_detailed(current.company_id)]


@router.get("/{driver_id}", response_model=DriverOut)
def get_driver(driver_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    row = DriverRepository(db).get_detailed(driver_id, current.company_id)
    if row is None:
        raise EntityNotFound("driver", driver_id)
    return _to_out(*row)


@router.post("", response_model=DriverOut, status_code=201)
def create_driver(body: DriverCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    emp = EmployeeRepository(db).get(body.employee_id)
    if emp is None or emp.company_id != current.company_id:
        raise ValidationFailed(f"employee {body.employee_id} not found for this company")
    if body.vehicle_id is not None:
        veh = db.query(Vehicle).filter(Vehicle.id == body.vehicle_id, Vehicle.company_id == current.company_id).first()
        if veh is None:
            raise ValidationFailed(f"vehicle {body.vehicle_id} not found for this company")
    data = {"employee_id": body.employee_id, "vehicle_id": body.vehicle_id,
            "drivers_license_number": body.drivers_license_number,
            "skills": _coerce_skills(body.skills)}
    d = DriverRepository(db).create(data, current.user_id, current.company_id)
    row = DriverRepository(db).get_detailed(d.id, current.company_id)
    return _to_out(*row)


@router.put("/{driver_id}", response_model=DriverOut)
def update_driver(driver_id: int, body: DriverUpdate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = DriverRepository(db)
    d = repo.get(driver_id, current.company_id)
    if d is None:
        raise EntityNotFound("driver", driver_id)
    data = body.model_dump(exclude_unset=True)
    if "skills" in data and data["skills"] is not None:
        data["skills"] = _coerce_skills(data["skills"])
    repo.update(d, data, current.user_id)
    return _to_out(*repo.get_detailed(driver_id, current.company_id))


@router.delete("/{driver_id}", status_code=204)
def delete_driver(driver_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = DriverRepository(db)
    d = repo.get(driver_id, current.company_id)
    if d is None:
        raise EntityNotFound("driver", driver_id)
    repo.soft_delete(d, current.user_id)
