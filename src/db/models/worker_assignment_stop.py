from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    Integer, DateTime, Text, ForeignKey, Enum
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from src.db.models.base import Base
from sqlalchemy.sql import func
from src.core.enums import WorkerStopStatus

if TYPE_CHECKING:
    from src.db.models.worker_assignment import WorkerAssignment
    from src.db.models.order import Order
    from src.db.models.driver_route_stop import DriverRouteStop

class WorkerAssignmentStop(Base):
    """
    One order served by one worker, in sequence within that worker's day.

    Links the service side to the shuttle side: ``dropoff_stop_id`` /
    ``pickup_stop_id`` reference the DriverRouteStop legs that transported the
    worker to and from this order. Both are nullable — e.g. a worker taken
    directly to a consecutive order by the same driver may not have a distinct
    intervening dropoff stop.
    """
    __tablename__ = "worker_assignment_stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_assignment_id: Mapped[int] = mapped_column(Integer, ForeignKey("worker_assignments.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    service_start_estimated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    service_end_estimated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    dropoff_stop_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("driver_route_stops.id"), nullable=True)
    pickup_stop_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("driver_route_stops.id"), nullable=True)
    # ── mobile execution tracking (field worker reports these) ────────────────
    stop_status: Mapped[Optional[WorkerStopStatus]] = mapped_column(Enum(WorkerStopStatus), default=WorkerStopStatus.pending)
    actual_service_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_service_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    worker_assignment: Mapped["WorkerAssignment"] = relationship("WorkerAssignment", back_populates="stops")
    order: Mapped["Order"] = relationship("Order", back_populates="worker_assignment_stops")
    dropoff_stop: Mapped[Optional["DriverRouteStop"]] = relationship(
        "DriverRouteStop", back_populates="dropoffs", foreign_keys=[dropoff_stop_id]
    )
    pickup_stop: Mapped[Optional["DriverRouteStop"]] = relationship(
        "DriverRouteStop", back_populates="pickups", foreign_keys=[pickup_stop_id]
    )

    def __repr__(self):
        return f"<WorkerAssignmentStop wa={self.worker_assignment_id} order={self.order_id} seq={self.sequence_number}>"
