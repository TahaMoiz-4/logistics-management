from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    DateTime, String, Float, ForeignKey, Integer, Enum
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid
from src.core.enums import OperationalStatus, VehicleType

if TYPE_CHECKING:
    from src.db.models.company import Company
    from src.db.models.vehicle import Vehicle
    from src.db.models.driver_route import DriverRoute
    from src.db.models.employee import Employee

class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    employee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("employees.id"), nullable=True)
    vehicle_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("vehicles.id"), nullable=True)
    drivers_license_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    orders_completed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    kms_driven: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.0)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.0)
    skills: Mapped[list[VehicleType]] = mapped_column(ARRAY(Enum(VehicleType)), nullable=True)
    operational_status: Mapped[Optional[OperationalStatus]] = mapped_column(Enum(OperationalStatus), default=OperationalStatus.active)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="drivers")
    employee: Mapped[Optional["Employee"]] = relationship("Employee", back_populates="drivers")
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle", back_populates="driver")
    driver_routes: Mapped[list["DriverRoute"]] = relationship("DriverRoute", back_populates="driver")

    def __repr__(self):
        return f"<Driver id={self.id} vehicle_id={self.vehicle_id}"
