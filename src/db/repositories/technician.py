"""
src/db/repositories/technician.py

Technician has no company_id of its own — scoped via its Employee. Mirrors
NurseRepository.
"""

from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import Technician, Employee


class TechnicianRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_with_employee(self, company_id: int) -> list[tuple[Technician, Employee]]:
        return (
            self.db.query(Technician, Employee)
            .join(Employee, Technician.employee_id == Employee.id)
            .filter(Employee.company_id == company_id, Technician.deleted_at.is_(None))
            .order_by(Technician.id)
            .all()
        )

    def get_with_employee(self, tech_id: int, company_id: int) -> Optional[tuple[Technician, Employee]]:
        return (
            self.db.query(Technician, Employee)
            .join(Employee, Technician.employee_id == Employee.id)
            .filter(Technician.id == tech_id, Employee.company_id == company_id,
                    Technician.deleted_at.is_(None))
            .first()
        )

    def get(self, tech_id: int) -> Optional[Technician]:
        return self.db.query(Technician).filter(Technician.id == tech_id, Technician.deleted_at.is_(None)).first()

    def create(self, data: dict, actor_id: int) -> Technician:
        obj = Technician(created_by=actor_id, **data)
        self.db.add(obj); self.db.commit(); self.db.refresh(obj)
        return obj

    def update(self, obj: Technician, data: dict, actor_id: int) -> Technician:
        for k, v in data.items():
            if v is not None and hasattr(obj, k):
                setattr(obj, k, v)
        obj.updated_by = actor_id
        self.db.commit(); self.db.refresh(obj)
        return obj

    def soft_delete(self, obj: Technician, actor_id: int) -> None:
        from datetime import datetime, timezone
        obj.deleted_at = datetime.now(timezone.utc)
        obj.deleted_by = actor_id
        self.db.commit()
