"""
src/api/v1/meta.py

Reference data for the frontend: all enum values so selects/labels/filters can be
rendered without hardcoding. Skills are split by service type; the company-aware
`/meta/enums` also returns the caller's applicable skill set.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.api.v1.deps import get_current_user, CurrentUser
from src.db.models import Company
from src.core.enums import (
    OrderStatus, OrderPriority, PlanStatus, RouteStatus, StopType, VehicleType,
    FuelType, OperationalStatus, ServiceType, NurseClinicalSkill, TechnicianSkills,
    WorkerStopStatus, DevicePlatform,
)

router = APIRouter(prefix="/v1/meta", tags=["meta"])


def _vals(enum_cls) -> list[str]:
    return [e.value for e in enum_cls]


@router.get("/enums")
def get_enums(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """All enum values. `applicable_skills` is the caller's company skill set."""
    company = db.query(Company).filter(Company.id == current.company_id).first()
    st = company.service_type if company and company.service_type else None
    applicable = _vals(NurseClinicalSkill) if st == ServiceType.nurse else (
        _vals(TechnicianSkills) if st == ServiceType.technician else [])

    return {
        "order_status": _vals(OrderStatus),
        "order_priority": _vals(OrderPriority),
        "plan_status": _vals(PlanStatus),
        "route_status": _vals(RouteStatus),
        "stop_type": _vals(StopType),
        "worker_stop_status": _vals(WorkerStopStatus),
        "vehicle_type": _vals(VehicleType),
        "fuel_type": _vals(FuelType),
        "operational_status": _vals(OperationalStatus),
        "service_type": _vals(ServiceType),
        "device_platform": _vals(DevicePlatform),
        "nurse_skills": _vals(NurseClinicalSkill),
        "technician_skills": _vals(TechnicianSkills),
        "company_service_type": st.value if st else None,
        "applicable_skills": applicable,
    }
