"""
src/db/repositories/nurse.py

Nurse has no company_id of its own — it's scoped via its Employee. Reads join
Employee for name/contact/shift/availability.
"""

from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import Nurse, Employee


class NurseRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_with_employee(self, company_id: int) -> list[tuple[Nurse, Employee]]:
        return (
            self.db.query(Nurse, Employee)
            .join(Employee, Nurse.employee_id == Employee.id)
            .filter(Employee.company_id == company_id, Nurse.deleted_at.is_(None))
            .order_by(Nurse.id)
            .all()
        )

    def get_with_employee(self, nurse_id: int, company_id: int) -> Optional[tuple[Nurse, Employee]]:
        return (
            self.db.query(Nurse, Employee)
            .join(Employee, Nurse.employee_id == Employee.id)
            .filter(Nurse.id == nurse_id, Employee.company_id == company_id,
                    Nurse.deleted_at.is_(None))
            .first()
        )

    def get(self, nurse_id: int) -> Optional[Nurse]:
        return self.db.query(Nurse).filter(Nurse.id == nurse_id, Nurse.deleted_at.is_(None)).first()

    def create(self, data: dict, actor_id: int) -> Nurse:
        obj = Nurse(created_by=actor_id, **data)
        self.db.add(obj); self.db.commit(); self.db.refresh(obj)
        return obj

    def update(self, obj: Nurse, data: dict, actor_id: int) -> Nurse:
        for k, v in data.items():
            if v is not None and hasattr(obj, k):
                setattr(obj, k, v)
        obj.updated_by = actor_id
        self.db.commit(); self.db.refresh(obj)
        return obj

    def soft_delete(self, obj: Nurse, actor_id: int) -> None:
        from datetime import datetime, timezone
        obj.deleted_at = datetime.now(timezone.utc)
        obj.deleted_by = actor_id
        self.db.commit()
