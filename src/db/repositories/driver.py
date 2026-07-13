"""
src/db/repositories/driver.py

Driver IS company-scoped (has company_id). Reads join Employee (name/contact/
availability) and Vehicle (plate/type).
"""

from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import Driver, Employee, Vehicle
from src.db.repositories.base import BaseRepository


class DriverRepository(BaseRepository[Driver]):
    model = Driver

    def list_detailed(self, company_id: int):
        """Returns list of (Driver, Employee|None, Vehicle|None)."""
        rows = (
            self.db.query(Driver, Employee, Vehicle)
            .outerjoin(Employee, Driver.employee_id == Employee.id)
            .outerjoin(Vehicle, Driver.vehicle_id == Vehicle.id)
            .filter(Driver.company_id == company_id, Driver.deleted_at.is_(None))
            .order_by(Driver.id)
            .all()
        )
        return rows

    def get_detailed(self, driver_id: int, company_id: int):
        return (
            self.db.query(Driver, Employee, Vehicle)
            .outerjoin(Employee, Driver.employee_id == Employee.id)
            .outerjoin(Vehicle, Driver.vehicle_id == Vehicle.id)
            .filter(Driver.id == driver_id, Driver.company_id == company_id,
                    Driver.deleted_at.is_(None))
            .first()
        )
