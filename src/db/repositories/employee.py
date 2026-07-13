"""
src/db/repositories/employee.py

DB access for Employee (field-worker identity + mobile login + availability).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import Employee, Nurse, Technician, Driver
from src.core.enums import OperationalStatus


class EmployeeRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── lookups ──────────────────────────────────────────────────────────────

    def get(self, employee_id: int) -> Optional[Employee]:
        return (
            self.db.query(Employee)
            .filter(Employee.id == employee_id, Employee.deleted_at.is_(None))
            .first()
        )

    def get_by_username(self, username: str) -> Optional[Employee]:
        return (
            self.db.query(Employee)
            .filter(Employee.username == username, Employee.deleted_at.is_(None))
            .first()
        )

    def list_for_company(self, company_id: int) -> list[Employee]:
        return (
            self.db.query(Employee)
            .filter(Employee.company_id == company_id, Employee.deleted_at.is_(None))
            .order_by(Employee.id)
            .all()
        )

    # ── role resolution (which domain row backs this employee) ───────────────

    def role_for(self, employee_id: int) -> Optional[str]:
        """
        Return 'nurse' | 'technician' | 'driver' depending on which domain table
        holds a row for this employee, else None. A given employee is expected to
        occupy exactly one role.
        """
        if self.db.query(Nurse.id).filter(Nurse.employee_id == employee_id).first():
            return "nurse"
        if self.db.query(Technician.id).filter(Technician.employee_id == employee_id).first():
            return "technician"
        if self.db.query(Driver.id).filter(Driver.employee_id == employee_id).first():
            return "driver"
        return None

    def worker_row_for(self, employee_id: int):
        """Return the (role, domain_row) for an employee, or (None, None)."""
        n = self.db.query(Nurse).filter(Nurse.employee_id == employee_id).first()
        if n:
            return "nurse", n
        t = self.db.query(Technician).filter(Technician.employee_id == employee_id).first()
        if t:
            return "technician", t
        d = self.db.query(Driver).filter(Driver.employee_id == employee_id).first()
        if d:
            return "driver", d
        return None, None

    # ── availability ─────────────────────────────────────────────────────────

    def set_availability(self, employee_id: int, available: bool,
                         reason: Optional[str] = None) -> Optional[Employee]:
        emp = self.get(employee_id)
        if emp is None:
            return None
        emp.operational_status = (
            OperationalStatus.active if available else OperationalStatus.suspended
        )
        emp.unavailable_reason = None if available else reason
        emp.status_changed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(emp)
        return emp
