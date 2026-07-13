"""
src/db/repositories/worker_assignment.py

Read side for the mobile "my-assignments" feed and for status/complete writes.

A worker's jobs = WorkerAssignmentStops belonging to WorkerAssignments whose
worker_id/worker_type match, within plans that have been APPROVED (dispatched).
Draft/optimizing plans are not shown to field workers.
"""

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import (
    WorkerAssignment, WorkerAssignmentStop, RoutePlan, Order, Location, DriverRoute,
)
from src.core.enums import ServiceType, PlanStatus


class WorkerAssignmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def stops_for_worker(
        self, worker_id: int, worker_type: ServiceType,
        on_date: Optional[date] = None, only_dispatched: bool = True,
    ):
        """
        Returns list of (WorkerAssignmentStop, Order, Location, RoutePlan) for a
        worker, optionally filtered to a plan date. Ordered by plan date then
        the worker's service sequence.
        """
        q = (
            self.db.query(WorkerAssignmentStop, Order, Location, RoutePlan)
            .join(WorkerAssignment, WorkerAssignmentStop.worker_assignment_id == WorkerAssignment.id)
            .join(RoutePlan, WorkerAssignment.plan_id == RoutePlan.id)
            .join(Order, WorkerAssignmentStop.order_id == Order.id)
            .outerjoin(Location, Order.location_id == Location.id)
            .filter(
                WorkerAssignment.worker_id == worker_id,
                WorkerAssignment.worker_type == worker_type,
                WorkerAssignmentStop.deleted_at.is_(None),
            )
        )
        if only_dispatched:
            q = q.filter(RoutePlan.status.in_([PlanStatus.dispatched, PlanStatus.completed]))
        if on_date is not None:
            q = q.filter(RoutePlan.planned_date == on_date)
        return q.order_by(RoutePlan.planned_date, WorkerAssignmentStop.sequence_number).all()

    def get_stop(self, stop_id: int) -> Optional[WorkerAssignmentStop]:
        return (
            self.db.query(WorkerAssignmentStop)
            .filter(WorkerAssignmentStop.id == stop_id,
                    WorkerAssignmentStop.deleted_at.is_(None))
            .first()
        )

    def owner_worker(self, stop: WorkerAssignmentStop) -> tuple[int, ServiceType]:
        """(worker_id, worker_type) that owns a stop — for authorization checks."""
        wa = (
            self.db.query(WorkerAssignment)
            .filter(WorkerAssignment.id == stop.worker_assignment_id)
            .first()
        )
        return (wa.worker_id, wa.worker_type) if wa else (None, None)

    def route_polyline_for_stop(self, stop: WorkerAssignmentStop) -> Optional[dict]:
        """
        The worker rides a driver's route; the polyline for their day is that
        driver route's geometry. Resolve via the stop's dropoff/pickup driver
        stop -> driver_route.geometry. Best-effort (may be None).
        """
        from src.db.models import DriverRouteStop
        drs_id = stop.dropoff_stop_id or stop.pickup_stop_id
        if drs_id is None:
            return None
        drs = self.db.query(DriverRouteStop).filter(DriverRouteStop.id == drs_id).first()
        if drs is None:
            return None
        dr = self.db.query(DriverRoute).filter(DriverRoute.id == drs.driver_route_id).first()
        return dr.geometry if dr else None
