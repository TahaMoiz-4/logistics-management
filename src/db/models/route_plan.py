from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, Integer, Float, DateTime, Date, ForeignKey, Enum, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid
from src.core.enums import PlanStatus

if TYPE_CHECKING:
    from src.db.models.company import Company
    from src.db.models.depot import Depot
    from src.db.models.driver_route import DriverRoute
    from src.db.models.worker_assignment import WorkerAssignment

class RoutePlan(Base):
    __tablename__ = "route_plans"

    id: Mapped[str] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    depot_id: Mapped[str] = mapped_column(Integer, ForeignKey("depots.id"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[Optional[PlanStatus]] = mapped_column(Enum(PlanStatus), default=PlanStatus.draft)
    # snapshot of solver config at time of optimization, e.g. {"max_vehicles": 5}
    optimization_params: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    total_orders: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    total_routes: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    total_unserved: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    objective_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # full solver telemetry for the demo dashboard: per-iteration objective
    # trace, operator counts, cost breakdown, runtime, unserved reasons. See
    # src/services/alns/persistence.py build_diagnostics().
    solver_diagnostics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    optimized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="route_plans")
    depot: Mapped["Depot"] = relationship("Depot", back_populates="plans")
    driver_routes: Mapped[list["DriverRoute"]] = relationship("DriverRoute", back_populates="plan")
    worker_assignments: Mapped[list["WorkerAssignment"]] = relationship("WorkerAssignment", back_populates="plan")

    def __repr__(self):
        return f"<RoutePlan id={self.id} date={self.planned_date} status={self.status}>"
