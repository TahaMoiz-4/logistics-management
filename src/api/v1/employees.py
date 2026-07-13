"""
src/api/v1/employees.py

Full CRUD for employees (field-worker identity). Employees underlie nurses/
technicians/drivers and hold the mobile login + availability. GET derives the
role from which domain table backs the employee.
"""

from __future__ import annotations

from datetime import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models import Employee
from src.db.repositories.employee import EmployeeRepository
from src.api.v1.deps import get_current_user, CurrentUser
from src.exceptions.common import EntityNotFound, DuplicateEntity, ValidationFailed
from src.core.security import hash_password
from src.schemas.employee import EmployeeOut, EmployeeCreate, EmployeeUpdate

router = APIRouter(prefix="/v1/employees", tags=["employees"])


def _parse_time(s):
    if not s:
        return None
    try:
        h, m = s.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        raise ValidationFailed(f"invalid time '{s}', expected HH:MM")


def _fmt_time(t):
    return t.strftime("%H:%M") if t else None


def _to_out(repo: EmployeeRepository, e: Employee) -> EmployeeOut:
    return EmployeeOut(
        id=e.id, name=e.name, company_id=e.company_id,
        contact_number=e.contact_number, contact_email=e.contact_email, cnic=e.cnic,
        shift_start=_fmt_time(e.shift_start), shift_end=_fmt_time(e.shift_end),
        operational_status=e.operational_status.value if e.operational_status else None,
        unavailable_reason=e.unavailable_reason,
        role=repo.role_for(e.id), has_login=bool(e.username),
    )


@router.get("", response_model=list[EmployeeOut])
def list_employees(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = EmployeeRepository(db)
    return [_to_out(repo, e) for e in repo.list_for_company(current.company_id)]


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = EmployeeRepository(db)
    e = repo.get(employee_id)
    if e is None or e.company_id != current.company_id:
        raise EntityNotFound("employee", employee_id)
    return _to_out(repo, e)


@router.post("", response_model=EmployeeOut, status_code=201)
def create_employee(body: EmployeeCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = EmployeeRepository(db)
    if body.username and repo.get_by_username(body.username):
        raise DuplicateEntity("employee", "username", body.username)
    e = Employee(
        name=body.name, company_id=current.company_id,
        contact_number=body.contact_number, contact_email=body.contact_email, cnic=body.cnic,
        shift_start=_parse_time(body.shift_start), shift_end=_parse_time(body.shift_end),
        username=body.username,
        password_hash=hash_password(body.password) if body.password else None,
        created_by=current.user_id,
    )
    db.add(e); db.commit(); db.refresh(e)
    return _to_out(repo, e)


@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, body: EmployeeUpdate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = EmployeeRepository(db)
    e = repo.get(employee_id)
    if e is None or e.company_id != current.company_id:
        raise EntityNotFound("employee", employee_id)
    data = body.model_dump(exclude_unset=True)
    if "username" in data and data["username"] and data["username"] != e.username:
        if repo.get_by_username(data["username"]):
            raise DuplicateEntity("employee", "username", data["username"])
    if "shift_start" in data:
        e.shift_start = _parse_time(data.pop("shift_start"))
    if "shift_end" in data:
        e.shift_end = _parse_time(data.pop("shift_end"))
    if data.get("password"):
        e.password_hash = hash_password(data.pop("password"))
    else:
        data.pop("password", None)
    if data.get("operational_status"):
        from src.core.enums import OperationalStatus
        e.operational_status = OperationalStatus(data.pop("operational_status"))
    for k, v in data.items():
        if v is not None and hasattr(e, k):
            setattr(e, k, v)
    e.updated_by = current.user_id
    db.commit(); db.refresh(e)
    return _to_out(repo, e)


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    repo = EmployeeRepository(db)
    e = repo.get(employee_id)
    if e is None or e.company_id != current.company_id:
        raise EntityNotFound("employee", employee_id)
    e.deleted_at = datetime.now(timezone.utc)
    e.deleted_by = current.user_id
    db.commit()
