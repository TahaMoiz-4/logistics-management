"""
src/api/v1/tracking.py

Web dashboard real-time views (polling; SSE is a future upgrade):
  * GET /v1/tracking/live          -> latest position per active worker/vehicle
  * GET /v1/workers/availability   -> roster: who's available/unavailable + why + contact
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models import (
    Nurse, Technician, Driver, Employee, Vehicle,
    WorkerPositionEvent, VehiclePositionEvent, Company,
)
from src.core.enums import ServiceType, OperationalStatus
from src.api.v1.deps import get_current_user, CurrentUser
from src.schemas.tracking import LivePosition, LiveTrackingOut, AvailabilityRosterEntry

router = APIRouter(tags=["tracking"])


# ── live positions ───────────────────────────────────────────────────────────

@router.get("/v1/tracking/live", response_model=LiveTrackingOut)
def live_tracking(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Latest known position of each of the company's workers + vehicles, with
    contact info (for click-popups) and recency flags. Positions older than
    TRACKING_DROP_AFTER_MIN are omitted; positions older than
    TRACKING_STALE_AFTER_SEC are flagged is_stale (the map greys them out).
    """
    from src.core.config import settings
    from src.db.models import Driver

    company_id = current.company_id
    company = db.query(Company).filter(Company.id == company_id).first()
    st = company.service_type if company else ServiceType.nurse

    now = datetime.now(timezone.utc)
    stale_after = settings.TRACKING_STALE_AFTER_SEC
    drop_after_sec = settings.TRACKING_DROP_AFTER_MIN * 60

    def _recency(recorded_at):
        """(seconds_ago, is_stale, keep)."""
        if recorded_at is None:
            return None, True, True
        # A client may send a naive timestamp (no offset); treat it as UTC so the
        # subtraction is valid rather than raising on naive-vs-aware.
        if recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=timezone.utc)
        secs = int((now - recorded_at).total_seconds())
        # Guard against a client clock slightly ahead of the server: never report
        # a negative "seconds ago" (would surface as e.g. "-17937s ago").
        if secs < 0:
            secs = 0
        return secs, (secs > stale_after), (secs <= drop_after_sec)

    positions: list[LivePosition] = []

    # workers (nurse or technician per company type)
    WorkerModel = Nurse if st == ServiceType.nurse else Technician
    worker_rows = (
        db.query(WorkerModel, Employee)
        .join(Employee, WorkerModel.employee_id == Employee.id)
        .filter(Employee.company_id == company_id, WorkerModel.deleted_at.is_(None))
        .all()
    )
    for w, emp in worker_rows:
        latest = (
            db.query(WorkerPositionEvent)
            .filter(WorkerPositionEvent.worker_id == w.id,
                    WorkerPositionEvent.worker_type == st)
            .order_by(WorkerPositionEvent.recorded_at.desc())
            .first()
        )
        if not latest:
            continue
        secs, is_stale, keep = _recency(latest.recorded_at)
        if not keep:
            continue
        positions.append(LivePosition(
            subject_type=st.value, subject_id=w.id, name=emp.name,
            lat=latest.lat, lng=latest.lng, recorded_at=latest.recorded_at,
            employee_id=emp.id, employee_code=f"EMP-{emp.id}",
            contact_number=emp.contact_number,
            seconds_ago=secs, is_stale=is_stale,
        ))

    # vehicles (drivers report to VehiclePositionEvent) — attach the driver's
    # employee contact so a vehicle dot popup shows who's driving it.
    vehicles = db.query(Vehicle).filter(Vehicle.company_id == company_id, Vehicle.deleted_at.is_(None)).all()
    for v in vehicles:
        latest = (
            db.query(VehiclePositionEvent)
            .filter(VehiclePositionEvent.vehicle_id == v.id)
            .order_by(VehiclePositionEvent.recorded_at.desc())
            .first()
        )
        if not latest:
            continue
        secs, is_stale, keep = _recency(latest.recorded_at)
        if not keep:
            continue
        driver = db.query(Driver).filter(Driver.vehicle_id == v.id, Driver.deleted_at.is_(None)).first()
        drv_emp = None
        if driver and driver.employee_id:
            drv_emp = db.query(Employee).filter(Employee.id == driver.employee_id).first()
        positions.append(LivePosition(
            subject_type="vehicle", subject_id=v.id,
            name=(drv_emp.name if drv_emp else v.license_plate),
            lat=latest.lat, lng=latest.lng, recorded_at=latest.recorded_at,
            employee_id=(drv_emp.id if drv_emp else None),
            employee_code=(f"EMP-{drv_emp.id}" if drv_emp else None),
            contact_number=(drv_emp.contact_number if drv_emp else None),
            seconds_ago=secs, is_stale=is_stale,
        ))

    return LiveTrackingOut(positions=positions, as_of=now, stale_after_sec=stale_after)


# ── availability roster ──────────────────────────────────────────────────────

@router.get("/v1/tracking/availability", response_model=list[AvailabilityRosterEntry])
def availability_roster(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Every field worker with their availability + reason + contact, so the admin
    can see at a glance who can be assigned and who's out (and why / how to reach
    them). Availability lives on Employee (the shared identity).
    """
    repo_emps = (
        db.query(Employee)
        .filter(Employee.company_id == current.company_id, Employee.deleted_at.is_(None))
        .order_by(Employee.id)
        .all()
    )
    from src.db.repositories.employee import EmployeeRepository
    role_repo = EmployeeRepository(db)
    out = []
    for e in repo_emps:
        status = e.operational_status or OperationalStatus.active
        out.append(AvailabilityRosterEntry(
            employee_id=e.id, name=e.name, role=role_repo.role_for(e.id),
            contact_number=e.contact_number, contact_email=e.contact_email,
            operational_status=status.value,
            available=(status == OperationalStatus.active),
            unavailable_reason=e.unavailable_reason, since=e.status_changed_at,
        ))
    return out
