from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, Float, Numeric, DateTime, ForeignKey, Enum, Integer, Index
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from src.db.models.base import Base, gen_uuid
from src.core.enums import PositionSource

if TYPE_CHECKING:
    from src.db.models.vehicle import Vehicle
    from src.db.models.driver_route import DriverRoute

class VehiclePositionEvent(Base):
    """
    Append-only log of vehicle positions.

    In pre-trip mode this table is empty.
    When live tracking is active (real GPS or simulator), rows are
    inserted via POST /vehicles/{id}/position and trigger re-routing logic.
    """
    __tablename__ = "vehicle_position_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, ForeignKey("vehicles.id"), nullable=False)
    driver_route_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("driver_routes.id"), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    h3_index: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    speed_kmh: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    source: Mapped[Optional[PositionSource]] = mapped_column(Enum(PositionSource), default=PositionSource.gps)

    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="positions")
    driver_route: Mapped[Optional["DriverRoute"]] = relationship("DriverRoute", back_populates="positions")

    __table_args__ = (
        Index("ix_position_vehicle_time", "vehicle_id", "recorded_at"),
    )

    def __repr__(self):
        return f"<VehiclePositionEvent vehicle={self.vehicle_id} at={self.recorded_at}>"
