from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    Integer, DateTime, ForeignKey, Enum
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from src.db.models.base import Base
from sqlalchemy.sql import func
from src.core.enums import StopType

if TYPE_CHECKING:
    from src.db.models.driver_route import DriverRoute
    from src.db.models.location import Location
    from src.db.models.worker_assignment_stop import WorkerAssignmentStop

class DriverRouteStop(Base):
    """
    One leg of a driver's physical route: arriving at a location to drop off
    or pick up a worker, or a depot start/end.

    ``stop_type`` is depot_start | dropoff | pickup | depot_end. A single stop
    can serve multiple workers (a van dropping two nurses at nearby orders),
    so WorkerAssignmentStop references this via dropoff_stop_id / pickup_stop_id
    rather than a 1:1 link.

    Replaces the old placeholder ``RouteStop`` model.
    """
    __tablename__ = "driver_route_stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    driver_route_id: Mapped[int] = mapped_column(Integer, ForeignKey("driver_routes.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_type: Mapped[StopType] = mapped_column(Enum(StopType), nullable=False)
    eta: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    etd: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    distance_from_prev_m: Mapped[Optional[int]] = mapped_column(Integer)
    time_from_prev_sec: Mapped[Optional[int]] = mapped_column(Integer)
    # filled in real-time when live tracking is active
    arrived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    departed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    driver_route: Mapped["DriverRoute"] = relationship("DriverRoute", back_populates="stops")
    location: Mapped["Location"] = relationship("Location", back_populates="driver_route_stops")
    # worker service events that this stop drops off / picks up
    dropoffs: Mapped[list["WorkerAssignmentStop"]] = relationship(
        "WorkerAssignmentStop", back_populates="dropoff_stop", foreign_keys="WorkerAssignmentStop.dropoff_stop_id"
    )
    pickups: Mapped[list["WorkerAssignmentStop"]] = relationship(
        "WorkerAssignmentStop", back_populates="pickup_stop", foreign_keys="WorkerAssignmentStop.pickup_stop_id"
    )

    def __repr__(self):
        return f"<DriverRouteStop route={self.driver_route_id} seq={self.sequence_number} type={self.stop_type}>"
