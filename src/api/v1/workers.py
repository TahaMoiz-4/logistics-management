"""
src/api/v1/workers.py

Full CRUD for the company's field workers (nurses OR technicians, chosen by the
company's service_type). A worker row references an Employee for identity; skills
use the service-type's skill enum. Availability/contact come from the Employee.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models import Company, Nurse, Technician, Employee
from src.db.repositories.nurse import NurseRepository
from src.db.repositories.technician import TechnicianRepository
from src.db.repositories.employee import EmployeeRepository
from src.api.v1.deps import get_current_user, CurrentUser
from src.exceptions.common import EntityNotFound, ValidationFailed
from src.core.enums import ServiceType, NurseClinicalSkill, TechnicianSkills
from src.schemas.worker import WorkerOut, WorkerCreate, WorkerUpdate

router = APIRouter(prefix="/v1/workers", tags=["workers"])


def _service_type(db: Session, company_id: int) -> ServiceType:
    c = db.query(Company).filter(Company.id == company_id).first()
    if c is None or c.service_type is None:
        raise ValidationFailed("company has no service_type set")
    return c.service_type


def _skill_enum(st: ServiceType):
    return NurseClinicalSkill if st == ServiceType.nurse else TechnicianSkills


def _coerce_skills(st: ServiceType, skills: list[str]):
    enum = _skill_enum(st)
    out = []
    for s in skills or []:
        try:
            out.append(enum(s))
        except ValueError:
            raise ValidationFailed(f"invalid skill '{s}' for {st.value}")
    return out


def _fmt_time(t):
    return t.strftime("%H:%M") if t else None


def _to_out(st: ServiceType, worker, emp: Employee) -> WorkerOut:
    return WorkerOut(
        id=worker.id, worker_type=st.value, employee_id=worker.employee_id,
        name=emp.name if emp else None,
        contact_number=emp.contact_number if emp else None,
        contact_email=emp.contact_email if emp else None,
        skills=[s.value if hasattr(s, "value") else str(s) for s in (worker.skills or [])],
        rating=worker.rating, orders_completed=worker.orders_completed,
        operational_status=(emp.operational_status.value if emp and emp.operational_status else None),
        unavailable_reason=emp.unavailable_reason if emp else None,
        shift_start=_fmt_time(emp.shift_start) if emp else None,
        shift_end=_fmt_time(emp.shift_end) if emp else None,
    )


def _repo(db, st):
    return NurseRepository(db) if st == ServiceType.nurse else TechnicianRepository(db)


@router.get("", response_model=list[WorkerOut])
def list_workers(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    st = _service_type(db, current.company_id)
    rows = _repo(db, st).list_with_employee(current.company_id)
    return [_to_out(st, w, e) for w, e in rows]


@router.get("/{worker_id}", response_model=WorkerOut)
def get_worker(worker_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    st = _service_type(db, current.company_id)
    row = _repo(db, st).get_with_employee(worker_id, current.company_id)
    if row is None:
        raise EntityNotFound("worker", worker_id)
    return _to_out(st, row[0], row[1])


@router.post("", response_model=WorkerOut, status_code=201)
def create_worker(body: WorkerCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    st = _service_type(db, current.company_id)
    emp = EmployeeRepository(db).get(body.employee_id)
    if emp is None or emp.company_id != current.company_id:
        raise ValidationFailed(f"employee {body.employee_id} not found for this company")
    data = {"employee_id": body.employee_id,
            "skills": _coerce_skills(st, body.skills), "rating": body.rating}
    worker = _repo(db, st).create(data, current.user_id)
    return _to_out(st, worker, emp)


@router.put("/{worker_id}", response_model=WorkerOut)
def update_worker(worker_id: int, body: WorkerUpdate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    st = _service_type(db, current.company_id)
    repo = _repo(db, st)
    row = repo.get_with_employee(worker_id, current.company_id)
    if row is None:
        raise EntityNotFound("worker", worker_id)
    worker, emp = row
    data = body.model_dump(exclude_unset=True)
    if "skills" in data and data["skills"] is not None:
        data["skills"] = _coerce_skills(st, data["skills"])
    worker = repo.update(worker, data, current.user_id)
    return _to_out(st, worker, emp)


@router.delete("/{worker_id}", status_code=204)
def delete_worker(worker_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    st = _service_type(db, current.company_id)
    repo = _repo(db, st)
    row = repo.get_with_employee(worker_id, current.company_id)
    if row is None:
        raise EntityNotFound("worker", worker_id)
    repo.soft_delete(row[0], current.user_id)
