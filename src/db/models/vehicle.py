from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import (
    String, Integer, Numeric, ForeignKey, Enum, DateTime
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from src.db.models.base import Base, gen_uuid
from src.core.enums import VehicleType, FuelType, OperationalStatus
from sqlalchemy.sql import func

if TYPE_CHECKING:
    from src.db.models.company import Company
    from src.db.models.depot import Depot
    from src.db.models.driver import Driver
    from src.db.models.driver_route import DriverRoute
    from src.db.models.vehicle_position_event import VehiclePositionEvent

class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    depot_id: Mapped[int] = mapped_column(Integer, ForeignKey("depots.id"), nullable=False)
    license_plate: Mapped[str] = mapped_column(String(32), nullable=False)
    type: Mapped[VehicleType] = mapped_column(Enum(VehicleType), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    engine_cc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    max_volume_m3: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), nullable=True)
    seating_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_speed_kmh: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), default=40)
    fuel_type: Mapped[Optional[FuelType]] = mapped_column(Enum(FuelType), default=FuelType.petrol)
    fuel_average: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    monthly_maintenance_cost: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    operational_status: Mapped[Optional[OperationalStatus]] = mapped_column(Enum(OperationalStatus), default=OperationalStatus.active)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="vehicles")
    depot: Mapped["Depot"] = relationship("Depot", back_populates="vehicles")
    # cost_profile: Mapped[Optional["CostProfile"]] = relationship("CostProfile", back_populates="vehicles")
    driver: Mapped[Optional["Driver"]] = relationship("Driver", back_populates="vehicle", uselist=False)
    driver_routes: Mapped[list["DriverRoute"]] = relationship("DriverRoute", back_populates="vehicle")
    positions: Mapped[list["VehiclePositionEvent"]] = relationship("VehiclePositionEvent", back_populates="vehicle")

    def __repr__(self):
        return f"<Vehicle id={self.id} plate={self.license_plate}>"
