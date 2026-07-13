"""
src/api/v1/mobile.py

Backend API for the Flutter field-ops app. The app talks ONLY to this backend;
the web dashboard sees mobile-driven changes by reading DB state the backend
exposes elsewhere.

Auth: workers log in as an Employee (separate from web SysUser auth). All other
endpoints require the worker bearer token (get_current_worker).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.core.security import verify_password, issue_token, SUBJECT_EMPLOYEE
from src.core.enums import (
    ServiceType, WorkerStopStatus, OrderStatus, DevicePlatform, PositionSource,
)
from src.db.repositories.employee import EmployeeRepository
from src.db.repositories.device_token import DeviceTokenRepository
from src.db.repositories.worker_assignment import WorkerAssignmentRepository
from src.db.repositories.worker_position import WorkerPositionRepository
from src.api.v1.deps import get_current_worker, CurrentWorker
from src.exceptions.auth import InvalidCredentials
from src.exceptions.mobile import (
    NotAssignedToYou, StopNotFound, StopAlreadyCompleted, WorkerHasNoRole,
    InvalidStopStatus,
)
from src.schemas.auth import LoginRequest, WorkerLoginResponse, WorkerOut
from src.schemas.mobile import (
    FcmTokenRequest, AssignmentStopOut, StopStatusRequest, StopCompleteRequest,
    StopOut, PositionBatchRequest, PositionBatchResponse,
    AvailabilityRequest, AvailabilityOut,
)

router = APIRouter(prefix="/v1/mobile", tags=["mobile"])


def _fmt_time(t):
    return t.strftime("%H:%M") if t else None


# ── worker identity resolution ───────────────────────────────────────────────

def _worker_row_id_and_type(db: Session, worker: CurrentWorker):
    """
    Resolve the mobile worker (Employee) to the domain row id + ServiceType that
    WorkerAssignment/WorkerPositionEvent key on. Drivers can't have
    WorkerAssignments (they drive, not serve) — but they can report position.
    """
    role, row = EmployeeRepository(db).worker_row_for(worker.employee_id)
    if role is None:
        raise WorkerHasNoRole()
    st = ServiceType.nurse if role == "nurse" else (
        ServiceType.technician if role == "technician" else None)
    return (row.id if row else None), st, role


# ── auth ─────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=WorkerLoginResponse)
def worker_login(body: LoginRequest, db: Session = Depends(get_db)):
    repo = EmployeeRepository(db)
    emp = repo.get_by_username(body.username)
    if emp is None or not verify_password(body.password, emp.password_hash):
        raise InvalidCredentials()
    role = repo.role_for(emp.id)
    token = issue_token(emp.id, SUBJECT_EMPLOYEE, emp.company_id)
    return WorkerLoginResponse(
        token=token,
        worker=WorkerOut(
            employee_id=emp.id, name=emp.name, company_id=emp.company_id, role=role,
            contact_number=emp.contact_number, contact_email=emp.contact_email,
            operational_status=emp.operational_status.value if emp.operational_status else "active",
            shift_start=_fmt_time(emp.shift_start), shift_end=_fmt_time(emp.shift_end),
        ),
    )


@router.post("/auth/logout")
def worker_logout(worker: CurrentWorker = Depends(get_current_worker)):
    return {"status": "logged_out"}


@router.post("/auth/fcm-token")
def register_fcm_token(body: FcmTokenRequest, worker: CurrentWorker = Depends(get_current_worker),
                       db: Session = Depends(get_db)):
    try:
        platform = DevicePlatform(body.platform or "android")
    except ValueError:
        platform = DevicePlatform.android
    DeviceTokenRepository(db).register(worker.employee_id, body.token, platform)
    return {"status": "registered"}


# ── my assignments ───────────────────────────────────────────────────────────

@router.get("/my-assignments", response_model=list[AssignmentStopOut])
def my_assignments(
    on_date: date | None = Query(None, alias="date", description="filter to a plan date"),
    worker: CurrentWorker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """This worker's assigned jobs in dispatched plans, optionally for one date."""
    row_id, st, role = _worker_row_id_and_type(db, worker)
    if st is None:
        # drivers don't serve orders — no service assignments
        return []
    repo = WorkerAssignmentRepository(db)
    rows = repo.stops_for_worker(row_id, st, on_date=on_date, only_dispatched=True)
    out = []
    for stop, order, loc, plan in rows:
        raw = (order.required_nurse_skills if st == ServiceType.nurse else order.required_tech_skills) or []
        out.append(AssignmentStopOut(
            stop_id=stop.id, order_id=order.id, plan_id=plan.id, plan_date=plan.planned_date,
            sequence_number=stop.sequence_number,
            stop_status=stop.stop_status.value if stop.stop_status else "pending",
            order_name=order.name, address_text=loc.address_text if loc else None,
            lat=loc.lat if loc else None, lng=loc.lng if loc else None,
            required_skills=[s.value if hasattr(s, "value") else str(s) for s in raw],
            service_duration_min=order.service_duration_min,
            service_start_estimated=stop.service_start_estimated,
            service_end_estimated=stop.service_end_estimated,
            timewindow_start=order.timewindow_start, timewindow_end=order.timewindow_end,
            actual_service_start=stop.actual_service_start,
            actual_service_end=stop.actual_service_end,
            route_polyline=repo.route_polyline_for_stop(stop),
        ))
    return out


# ── status / complete ────────────────────────────────────────────────────────

_STATUS_MAP = {
    "en_route": WorkerStopStatus.en_route,
    "arrived": WorkerStopStatus.arrived,
    "in_progress": WorkerStopStatus.in_progress,
}


def _load_owned_stop(db: Session, stop_id: int, worker: CurrentWorker):
    row_id, st, role = _worker_row_id_and_type(db, worker)
    repo = WorkerAssignmentRepository(db)
    stop = repo.get_stop(stop_id)
    if stop is None:
        raise StopNotFound(stop_id)
    owner_id, owner_type = repo.owner_worker(stop)
    if owner_id != row_id or owner_type != st:
        raise NotAssignedToYou()
    return stop


@router.post("/orders/{stop_id}/status", response_model=StopOut)
def update_stop_status(stop_id: int, body: StopStatusRequest,
                       worker: CurrentWorker = Depends(get_current_worker), db: Session = Depends(get_db)):
    stop = _load_owned_stop(db, stop_id, worker)
    if stop.stop_status == WorkerStopStatus.completed:
        raise StopAlreadyCompleted()
    new_status = _STATUS_MAP.get(body.status)
    if new_status is None:
        raise InvalidStopStatus(body.status)
    stop.stop_status = new_status
    if new_status == WorkerStopStatus.in_progress and stop.actual_service_start is None:
        stop.actual_service_start = datetime.now(timezone.utc)
    db.commit(); db.refresh(stop)
    return _stop_out(db, stop)


@router.post("/orders/{stop_id}/complete", response_model=StopOut)
def complete_stop(stop_id: int, body: StopCompleteRequest,
                  worker: CurrentWorker = Depends(get_current_worker), db: Session = Depends(get_db)):
    stop = _load_owned_stop(db, stop_id, worker)
    if stop.stop_status == WorkerStopStatus.completed:
        raise StopAlreadyCompleted()
    now = body.completed_at or datetime.now(timezone.utc)
    stop.stop_status = WorkerStopStatus.completed
    if stop.actual_service_start is None:
        stop.actual_service_start = now
    stop.actual_service_end = now
    stop.completion_notes = body.notes
    # roll up: mark the order delivered
    from src.db.models import Order
    order = db.query(Order).filter(Order.id == stop.order_id).first()
    if order is not None:
        order.status = OrderStatus.delivered
    db.commit(); db.refresh(stop)
    return _stop_out(db, stop)


def _stop_out(db: Session, stop) -> StopOut:
    from src.db.models import Order
    order = db.query(Order).filter(Order.id == stop.order_id).first()
    return StopOut(
        stop_id=stop.id, order_id=stop.order_id,
        stop_status=stop.stop_status.value if stop.stop_status else "pending",
        actual_service_start=stop.actual_service_start,
        actual_service_end=stop.actual_service_end,
        order_status=order.status.value if order and order.status else "pending",
    )


# ── position ─────────────────────────────────────────────────────────────────

@router.post("/position", response_model=PositionBatchResponse)
def report_position(body: PositionBatchRequest, worker: CurrentWorker = Depends(get_current_worker),
                    db: Session = Depends(get_db)):
    """
    Ingest a batch of GPS pings.
      * nurse / technician -> WorkerPositionEvent (keyed by their domain row + type)
      * driver             -> VehiclePositionEvent (they always drive a vehicle);
        WorkerPositionEvent.worker_type is ServiceType (nurse|technician) and has
        no 'driver' member, so a driver's live location belongs on the vehicle log.
    """
    role, row = EmployeeRepository(db).worker_row_for(worker.employee_id)
    if role is None:
        raise WorkerHasNoRole()

    if role == "driver":
        n = _record_driver_positions(db, row, body)
    else:
        worker_type = ServiceType.nurse if role == "nurse" else ServiceType.technician
        n = WorkerPositionRepository(db).record_batch(
            worker_id=row.id, worker_type=worker_type,
            pings=[p.model_dump() for p in body.pings], source=PositionSource.gps,
        )
    return PositionBatchResponse(recorded=n)


def _record_driver_positions(db: Session, driver, body: PositionBatchRequest) -> int:
    """Append a driver's pings to VehiclePositionEvent (needs their vehicle)."""
    from src.db.models import VehiclePositionEvent
    from src.services.h3_service import latlng_to_h3
    if driver.vehicle_id is None:
        # no vehicle assigned — nothing to key the vehicle log on; skip gracefully
        return 0
    n = 0
    for p in body.pings:
        db.add(VehiclePositionEvent(
            vehicle_id=driver.vehicle_id, lat=p.lat, lng=p.lng,
            h3_index=latlng_to_h3(p.lat, p.lng),
            recorded_at=p.recorded_at or datetime.utcnow(), source=PositionSource.gps,
        ))
        n += 1
    db.commit()
    return n


# ── availability ─────────────────────────────────────────────────────────────

@router.post("/availability", response_model=AvailabilityOut)
def set_availability(body: AvailabilityRequest, worker: CurrentWorker = Depends(get_current_worker),
                     db: Session = Depends(get_db)):
    emp = EmployeeRepository(db).set_availability(
        worker.employee_id, body.available, body.reason)
    return AvailabilityOut(
        employee_id=emp.id, available=(emp.operational_status.value == "active"),
        operational_status=emp.operational_status.value,
        reason=emp.unavailable_reason, since=emp.status_changed_at,
    )


@router.get("/availability/me", response_model=AvailabilityOut)
def my_availability(worker: CurrentWorker = Depends(get_current_worker), db: Session = Depends(get_db)):
    emp = EmployeeRepository(db).get(worker.employee_id)
    return AvailabilityOut(
        employee_id=emp.id,
        available=(emp.operational_status.value == "active" if emp.operational_status else True),
        operational_status=emp.operational_status.value if emp.operational_status else "active",
        reason=emp.unavailable_reason, since=emp.status_changed_at,
    )
