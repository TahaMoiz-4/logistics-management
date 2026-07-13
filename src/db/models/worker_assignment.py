from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    Integer, DateTime, ForeignKey, Enum
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from src.db.models.base import Base
from sqlalchemy.sql import func
from src.core.enums import ServiceType

if TYPE_CHECKING:
    from src.db.models.route_plan import RoutePlan
    from src.db.models.worker_assignment_stop import WorkerAssignmentStop

class WorkerAssignment(Base):
    """
    One nurse/technician's service day within a plan (the "service" path).

    This is the provider side of the DARP-hybrid: the ordered sequence of
    orders a single worker serves. The worker doesn't drive — they are shuttled
    between orders by drivers (see DriverRoute). Each served order is a
    WorkerAssignmentStop that points back at the driver stops that dropped the
    worker off and picked them up.

    ``worker_id`` is a soft reference into either the ``nurses`` or
    ``technicians`` table, disambiguated by ``worker_type`` — not a hard FK,
    since it can target one of two tables.
    """
    __tablename__ = "worker_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("route_plans.id"), nullable=False)
    worker_id: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_type: Mapped[ServiceType] = mapped_column(Enum(ServiceType), nullable=False)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    plan: Mapped["RoutePlan"] = relationship("RoutePlan", back_populates="worker_assignments")
    stops: Mapped[list["WorkerAssignmentStop"]] = relationship(
        "WorkerAssignmentStop", back_populates="worker_assignment", order_by="WorkerAssignmentStop.sequence_number"
    )

    def __repr__(self):
        return f"<WorkerAssignment id={self.id} worker={self.worker_type}:{self.worker_id}>"
