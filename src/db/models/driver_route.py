from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    Integer, Numeric, DateTime, ForeignKey, Enum, JSON
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from src.db.models.base import Base
from src.core.enums import RouteStatus
from sqlalchemy.sql import func

if TYPE_CHECKING:
    from src.db.models.route_plan import RoutePlan
    from src.db.models.vehicle import Vehicle
    from src.db.models.driver import Driver
    from src.db.models.driver_route_stop import DriverRouteStop
    from src.db.models.vehicle_position_event import VehiclePositionEvent

class DriverRoute(Base):
    """
    One driver+vehicle's physical route for a single plan (the "shuttle" path).

    This is the mover side of the DARP-hybrid: the sequence of depot/pickup/
    dropoff stops a driver drives. Workers (nurses/techs) ride along and are
    dropped off / picked up at these stops — see WorkerAssignment for the
    service side that references these stops.

    Replaces the old placeholder ``Route`` model.
    """
    __tablename__ = "driver_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("route_plans.id"), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(Integer, ForeignKey("vehicles.id"), nullable=False)
    driver_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("drivers.id"))
    status: Mapped[Optional[RouteStatus]] = mapped_column(Enum(RouteStatus), default=RouteStatus.pending)
    total_distance_m: Mapped[Optional[int]] = mapped_column(Integer)
    total_time_sec: Mapped[Optional[int]] = mapped_column(Integer)
    total_fuel_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    estimated_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    departure_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # full path as GeoJSON LineString for map rendering
    geometry: Mapped[Optional[dict]] = mapped_column(JSON)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    plan: Mapped["RoutePlan"] = relationship("RoutePlan", back_populates="driver_routes")
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="driver_routes")
    driver: Mapped[Optional["Driver"]] = relationship("Driver", back_populates="driver_routes")
    stops: Mapped[list["DriverRouteStop"]] = relationship(
        "DriverRouteStop", back_populates="driver_route", order_by="DriverRouteStop.sequence_number"
    )
    positions: Mapped[list["VehiclePositionEvent"]] = relationship("VehiclePositionEvent", back_populates="driver_route")

    def __repr__(self):
        return f"<DriverRoute id={self.id} vehicle={self.vehicle_id} status={self.status}>"
