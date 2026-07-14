"""
src/api/v1/route_plans.py

Route-plan API: create + trigger a solve, watch it live over SSE, and read the
results (driver routes, worker assignments, unserved, diagnostics, map data).

Solve runs in a FastAPI BackgroundTask (worker thread); progress streams via the
in-process channel registry (progress.py) to the SSE endpoint.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from src.db.database import get_db
from src.db.models import (
    Company, Depot, Location, Order, RoutePlan,
    DriverRoute, DriverRouteStop, WorkerAssignment, WorkerAssignmentStop,
)
from src.core.enums import PlanStatus, OrderStatus, ServiceType
from src.services.alns.runner import run_solve
from src.api.v1 import progress
from src.api.v1.deps import get_current_user, CurrentUser
from src.exceptions.orders import (
    OrdersNotFound, OrdersNotOwned, OrdersNotServable, OrdersMissingServiceDate,
    OrdersSpanMultipleDates, PlannedDateMismatch, SelectionMissing, NoServableOrders,
)
from src.exceptions.common import EntityNotFound, CrossCompanyAccess
from src.exceptions.route_plans import (
    PlanNotReady, PlanAlreadyDispatched, PlanNotDeletable,
)
from src.core.enums import WorkerStopStatus
from src.services.notifications.fcm import notify_workers
from src.schemas.route_plan import (
    CreateRoutePlanRequest, CreateRoutePlanResponse, RoutePlanSummary,
    DriverRouteOut, DriverStopOut, WorkerAssignmentOut, WorkerStopOut,
    UnservedOrderOut, DiagnosticsOut, MapDataOut, ServableOrderOut,
    ApproveResponse,
)

router = APIRouter(prefix="/v1/route-plans", tags=["route-plans"])


# ---------------------------------------------------------------------------
# Create + trigger solve
# ---------------------------------------------------------------------------

@router.post("", response_model=CreateRoutePlanResponse, status_code=202)
def create_route_plan(
    body: CreateRoutePlanRequest,
    background: BackgroundTasks,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company_id = current.company_id

    depot_id = body.depot_id
    if depot_id is None:
        depot = db.query(Depot).filter(Depot.company_id == company_id).order_by(Depot.id).first()
        if depot is None:
            raise HTTPException(400, "company has no depot; pass depot_id")
        depot_id = depot.id

    # resolve which orders + which date this plan solves (see _resolve_selection)
    planned_date, order_ids = _resolve_selection(db, company_id, body)

    plan = RoutePlan(
        company_id=company_id, depot_id=depot_id, planned_date=planned_date,
        name=body.name, status=PlanStatus.optimizing, created_by=current.user_id,
        optimization_params=body.config_overrides or {},
    )
    db.add(plan); db.commit(); db.refresh(plan)

    # open a progress channel and kick the solve off in the background
    progress.create_channel(plan.id)
    background.add_task(
        run_solve,
        route_plan_id=plan.id,
        company_id=company_id,
        planned_date=planned_date,
        repair_mode=body.repair_mode,
        config_overrides=body.config_overrides,
        order_ids=order_ids,
        publish=lambda e: progress.publish(plan.id, e),
        finish=lambda e: progress.finish(plan.id, e),
    )

    return CreateRoutePlanResponse(
        route_plan_id=plan.id, status=plan.status.value,
        planned_date=planned_date, order_count=len(order_ids) if order_ids else 0,
        stream_url=f"/v1/route-plans/{plan.id}/stream",
    )


# servable order statuses (mirror the loader)
_SERVABLE = (OrderStatus.pending, OrderStatus.assigned)


def _resolve_selection(db: Session, company_id: int, body: CreateRoutePlanRequest):
    """
    Validate the order selection and resolve (planned_date, order_ids). company_id
    comes from the authenticated user, never the request body.

    * order_ids given  -> every ID must belong to the company, be servable
      (pending/assigned), have a service_date, and all share ONE service_date.
      That shared date is the planned_date (must match body.planned_date if the
      caller also passed one). Rejects (400) on any violation, listing offenders.
    * order_ids omitted -> body.planned_date is required; order_ids stays None
      so the loader picks up all servable orders on that date. If there are none,
      reject so the user isn't left with an empty plan.
    """
    if body.order_ids:
        ids = list(dict.fromkeys(body.order_ids))  # dedupe, keep order
        orders = db.query(Order).filter(Order.id.in_(ids)).all()
        found = {o.id: o for o in orders}

        missing = [i for i in ids if i not in found]
        if missing:
            raise OrdersNotFound(missing)

        wrong_company = [i for i in ids if found[i].company_id != company_id]
        if wrong_company:
            raise OrdersNotOwned(wrong_company)

        not_servable = [i for i in ids if found[i].status not in _SERVABLE]
        if not_servable:
            raise OrdersNotServable(not_servable)

        no_date = [i for i in ids if found[i].service_date is None]
        if no_date:
            raise OrdersMissingServiceDate(no_date)

        dates = {found[i].service_date for i in ids}
        if len(dates) > 1:
            raise OrdersSpanMultipleDates(dates)
        derived = dates.pop()
        if body.planned_date is not None and body.planned_date != derived:
            raise PlannedDateMismatch(body.planned_date, derived)
        return derived, ids

    # no order_ids -> need a date, solve all servable orders that day
    if body.planned_date is None:
        raise SelectionMissing()
    count = (
        db.query(Order)
        .filter(
            Order.company_id == company_id,
            Order.status.in_(_SERVABLE),
            Order.service_date == body.planned_date,
            Order.location_id.isnot(None),
        )
        .count()
    )
    if count == 0:
        raise NoServableOrders(company_id, body.planned_date)
    return body.planned_date, None


# ---------------------------------------------------------------------------
# SSE live progress
# ---------------------------------------------------------------------------

@router.get("/{plan_id}/stream")
async def stream_progress(plan_id: int):
    """
    Server-sent events streaming live solver progress. Yields each event the
    solve publishes (loading/solving/best/progress/persisting), then a final
    'done' (or 'error') event, then closes.
    """
    q = progress.get_channel(plan_id)
    if q is None:
        raise HTTPException(404, f"no active solve for plan {plan_id} (already finished?)")

    async def event_generator():
        loop = asyncio.get_event_loop()
        while True:
            # drain the thread-safe queue without blocking the event loop
            item = await loop.run_in_executor(None, q.get)
            if item is progress.DONE:
                progress.drop_channel(plan_id)
                yield {"event": "close", "data": json.dumps({"event": "close"})}
                break
            evt = item.get("event", "message")
            yield {"event": evt, "data": json.dumps(item)}

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Result summary
# ---------------------------------------------------------------------------

def _get_plan(db: Session, plan_id: int, company_id: int) -> RoutePlan:
    plan = db.query(RoutePlan).filter(RoutePlan.id == plan_id).one_or_none()
    if plan is None:
        raise EntityNotFound("route_plan", plan_id)
    if plan.company_id != company_id:
        raise CrossCompanyAccess("route plan")
    return plan


def _summary(plan) -> RoutePlanSummary:
    return RoutePlanSummary(
        id=plan.id, company_id=plan.company_id, depot_id=plan.depot_id,
        planned_date=plan.planned_date, status=plan.status.value if plan.status else "draft",
        name=plan.name, objective_value=plan.objective_value,
        total_orders=plan.total_orders, total_routes=plan.total_routes,
        total_unserved=plan.total_unserved, optimized_at=plan.optimized_at,
        created_at=plan.created_at,
    )


@router.get("", response_model=list[RoutePlanSummary])
def list_route_plans(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """All route plans for the company (history), newest planned_date first."""
    from src.db.repositories.route_plan import RoutePlanRepository
    return [_summary(p) for p in RoutePlanRepository(db).list_for_company(current.company_id)]


@router.get("/{plan_id}", response_model=RoutePlanSummary)
def get_route_plan(plan_id: int, current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    return _summary(_get_plan(db, plan_id, current.company_id))


@router.post("/{plan_id}/approve", response_model=ApproveResponse)
def approve_route_plan(plan_id: int, current: CurrentUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """
    Approve a solved (ready) plan: dispatch it, mark its orders assigned,
    initialize each worker stop to pending, and push a job alert to each
    assigned worker's devices. Workers are NOT locked — a worker can hold jobs
    across multiple plans, each stop with its own status.
    """
    plan = _get_plan(db, plan_id, current.company_id)
    if plan.status == PlanStatus.dispatched:
        raise PlanAlreadyDispatched()
    if plan.status != PlanStatus.ready:
        raise PlanNotReady(plan.status.value if plan.status else "draft")

    # 1. mark the plan's orders assigned + init stop statuses; collect worker employee_ids
    assignments = db.query(WorkerAssignment).filter(WorkerAssignment.plan_id == plan_id).all()
    order_ids, worker_ids_by_type = set(), {}
    for wa in assignments:
        worker_ids_by_type.setdefault(wa.worker_type, set()).add(wa.worker_id)
        for stop in wa.stops:
            order_ids.add(stop.order_id)
            if stop.stop_status is None or stop.stop_status == WorkerStopStatus.pending:
                stop.stop_status = WorkerStopStatus.pending
    n_assigned = 0
    if order_ids:
        n_assigned = (
            db.query(Order)
            .filter(Order.id.in_(order_ids))
            .update({Order.status: OrderStatus.assigned}, synchronize_session=False)
        )

    plan.status = PlanStatus.dispatched
    plan.updated_by = current.user_id
    db.commit()

    # 2. resolve worker_id (domain row) -> employee_id, then notify their devices
    employee_ids = _assigned_employee_ids(db, worker_ids_by_type)
    summary = notify_workers(
        db, employee_ids,
        title="New route assigned",
        body=f"You have new job(s) for {plan.planned_date}.",
        data={"route_plan_id": str(plan_id), "planned_date": str(plan.planned_date)},
    )

    return ApproveResponse(
        route_plan_id=plan_id, status=plan.status.value,
        orders_marked_assigned=n_assigned,
        workers_notified=summary.get("sent", 0) or summary.get("would_send_to", 0),
        notify_mode=summary.get("mode", "none"),
    )


def _assigned_employee_ids(db: Session, worker_ids_by_type: dict) -> list[int]:
    """Map WorkerAssignment.worker_id (nurse/tech row id) -> Employee.id for notify."""
    from src.core.enums import ServiceType
    from src.db.models import Nurse, Technician
    emp_ids: set[int] = set()
    for worker_type, ids in worker_ids_by_type.items():
        model = Nurse if worker_type == ServiceType.nurse else Technician
        for row in db.query(model).filter(model.id.in_(ids)).all():
            if row.employee_id:
                emp_ids.add(row.employee_id)
    return list(emp_ids)


@router.delete("/{plan_id}", status_code=204)
def delete_route_plan(plan_id: int, current: CurrentUser = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """Soft-delete a plan. Dispatched/completed plans cannot be deleted."""
    from datetime import datetime, timezone
    plan = _get_plan(db, plan_id, current.company_id)
    if plan.status in (PlanStatus.dispatched, PlanStatus.completed):
        raise PlanNotDeletable(plan.status.value)
    plan.deleted_at = datetime.now(timezone.utc)
    plan.deleted_by = current.user_id
    db.commit()


# ---------------------------------------------------------------------------
# Driver routes
# ---------------------------------------------------------------------------

@router.get("/{plan_id}/driver-routes", response_model=list[DriverRouteOut])
def get_driver_routes(plan_id: int, current: CurrentUser = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    _get_plan(db, plan_id, current.company_id)
    routes = db.query(DriverRoute).filter(DriverRoute.plan_id == plan_id).all()
    loc_ids = {s.location_id for r in routes for s in r.stops}
    locs = {l.id: l for l in db.query(Location).filter(Location.id.in_(loc_ids)).all()} if loc_ids else {}

    out = []
    for r in routes:
        stops = []
        for s in sorted(r.stops, key=lambda x: x.sequence_number):
            loc = locs.get(s.location_id)
            stops.append(DriverStopOut(
                sequence_number=s.sequence_number, stop_type=s.stop_type.value,
                location_id=s.location_id,
                lat=loc.lat if loc else None, lng=loc.lng if loc else None,
                eta=s.eta, etd=s.etd,
                distance_from_prev_m=s.distance_from_prev_m,
                time_from_prev_sec=s.time_from_prev_sec,
            ))
        out.append(DriverRouteOut(
            id=r.id, driver_id=r.driver_id, vehicle_id=r.vehicle_id,
            status=r.status.value if r.status else "pending",
            total_distance_m=r.total_distance_m, total_time_sec=r.total_time_sec,
            stops=stops,
        ))
    return out


# ---------------------------------------------------------------------------
# Worker assignments
# ---------------------------------------------------------------------------

@router.get("/{plan_id}/worker-assignments", response_model=list[WorkerAssignmentOut])
def get_worker_assignments(plan_id: int, current: CurrentUser = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    _get_plan(db, plan_id, current.company_id)
    assignments = db.query(WorkerAssignment).filter(WorkerAssignment.plan_id == plan_id).all()

    # resolve order -> location for lat/lng on each service stop
    order_ids = {s.order_id for a in assignments for s in a.stops}
    orders = {o.id: o for o in db.query(Order).filter(Order.id.in_(order_ids)).all()} if order_ids else {}
    loc_ids = {o.location_id for o in orders.values() if o.location_id}
    locs = {l.id: l for l in db.query(Location).filter(Location.id.in_(loc_ids)).all()} if loc_ids else {}

    # resolve worker_id (soft ref into nurses/technicians per worker_type) -> name.
    # Batched: nurses.id/technicians.id -> employee_id -> Employee.name.
    from src.db.models import Nurse, Technician, Employee
    nurse_ids = {a.worker_id for a in assignments if a.worker_type == ServiceType.nurse}
    tech_ids = {a.worker_id for a in assignments if a.worker_type == ServiceType.technician}
    nurse_to_emp = {n.id: n.employee_id for n in db.query(Nurse).filter(Nurse.id.in_(nurse_ids)).all()} if nurse_ids else {}
    tech_to_emp = {t.id: t.employee_id for t in db.query(Technician).filter(Technician.id.in_(tech_ids)).all()} if tech_ids else {}
    emp_ids = set(nurse_to_emp.values()) | set(tech_to_emp.values())
    emp_names = {e.id: e.name for e in db.query(Employee).filter(Employee.id.in_(emp_ids)).all()} if emp_ids else {}

    def _worker_name(a) -> str | None:
        emp_id = (nurse_to_emp if a.worker_type == ServiceType.nurse else tech_to_emp).get(a.worker_id)
        return emp_names.get(emp_id) if emp_id else None

    out = []
    for a in assignments:
        stops = []
        for s in sorted(a.stops, key=lambda x: x.sequence_number):
            o = orders.get(s.order_id)
            loc = locs.get(o.location_id) if o else None
            stops.append(WorkerStopOut(
                sequence_number=s.sequence_number, order_id=s.order_id,
                lat=loc.lat if loc else None, lng=loc.lng if loc else None,
                service_start_estimated=s.service_start_estimated,
                service_end_estimated=s.service_end_estimated,
            ))
        out.append(WorkerAssignmentOut(
            id=a.id, worker_id=a.worker_id,
            worker_type=a.worker_type.value if a.worker_type else "nurse",
            worker_name=_worker_name(a),
            stops=stops,
        ))
    return out


# ---------------------------------------------------------------------------
# Unserved orders
# ---------------------------------------------------------------------------

@router.get("/{plan_id}/unserved", response_model=list[UnservedOrderOut])
def get_unserved(plan_id: int, current: CurrentUser = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    plan = _get_plan(db, plan_id, current.company_id)
    diag = plan.solver_diagnostics or {}
    return [UnservedOrderOut(order_id=u["order_id"], reason=u.get("reason", "unknown"))
            for u in diag.get("unserved", [])]


# ---------------------------------------------------------------------------
# Diagnostics (the demo dashboard payload)
# ---------------------------------------------------------------------------

@router.get("/{plan_id}/diagnostics", response_model=DiagnosticsOut)
def get_diagnostics(plan_id: int, current: CurrentUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    plan = _get_plan(db, plan_id, current.company_id)
    diag = plan.solver_diagnostics
    if not diag:
        raise HTTPException(409, f"plan {plan_id} has no diagnostics yet (status={plan.status.value if plan.status else '?'})")
    return DiagnosticsOut(**diag)


# ---------------------------------------------------------------------------
# Map data (spatial view)
# ---------------------------------------------------------------------------

@router.get("/{plan_id}/map-data", response_model=MapDataOut)
def get_map_data(plan_id: int, current: CurrentUser = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    plan = _get_plan(db, plan_id, current.company_id)

    depot = db.query(Depot).filter(Depot.id == plan.depot_id).one()
    depot_loc = db.query(Location).filter(Location.id == depot.location_id).one_or_none()
    depot_out = {
        "location_id": depot.location_id,
        "lat": depot_loc.lat if depot_loc else None,
        "lng": depot_loc.lng if depot_loc else None,
    }

    routes = db.query(DriverRoute).filter(DriverRoute.plan_id == plan_id).all()
    loc_ids = {s.location_id for r in routes for s in r.stops}
    locs = {l.id: l for l in db.query(Location).filter(Location.id.in_(loc_ids)).all()} if loc_ids else {}

    # batch-resolve driver + vehicle names for a human-readable legend
    from src.db.models import Driver, Vehicle, Employee
    driver_ids = {r.driver_id for r in routes if r.driver_id}
    vehicle_ids = {r.vehicle_id for r in routes if r.vehicle_id}
    drivers = {d.id: d for d in db.query(Driver).filter(Driver.id.in_(driver_ids)).all()} if driver_ids else {}
    emp_ids = {d.employee_id for d in drivers.values() if d.employee_id}
    emps = {e.id: e for e in db.query(Employee).filter(Employee.id.in_(emp_ids)).all()} if emp_ids else {}
    vehicles = {v.id: v for v in db.query(Vehicle).filter(Vehicle.id.in_(vehicle_ids)).all()} if vehicle_ids else {}

    driver_routes = []
    for r in routes:
        pts = []
        for s in sorted(r.stops, key=lambda x: x.sequence_number):
            loc = locs.get(s.location_id)
            pts.append({"seq": s.sequence_number, "stop_type": s.stop_type.value,
                        "lat": loc.lat if loc else None, "lng": loc.lng if loc else None})
        d = drivers.get(r.driver_id)
        drv_emp = emps.get(d.employee_id) if d and d.employee_id else None
        veh = vehicles.get(r.vehicle_id)
        driver_routes.append({
            "driver_route_id": r.id,
            "driver_id": r.driver_id,
            "driver_name": drv_emp.name if drv_emp else None,
            "vehicle_id": r.vehicle_id,
            "vehicle_plate": veh.license_plate if veh else None,
            "total_distance_m": r.total_distance_m,
            "total_time_sec": r.total_time_sec,
            "points": pts,
            # real road-following polyline (GeoJSON LineString/MultiLineString,
            # [lng,lat]); null if the solve fell back to straight-line mode
            "geometry": r.geometry,
        })

    # order markers — STRICTLY this plan's orders (not the whole company).
    # served: orders in this plan's worker assignments.
    # unserved: order ids the solver recorded as unassigned in solver_diagnostics.
    assignments = db.query(WorkerAssignment).filter(WorkerAssignment.plan_id == plan_id).all()
    served_order_to_worker = {s.order_id: a.worker_id for a in assignments for s in a.stops}
    unserved_ids = {
        u.get("order_id")
        for u in (plan.solver_diagnostics or {}).get("unserved", [])
        if u.get("order_id") is not None
    }
    plan_order_ids = set(served_order_to_worker) | unserved_ids
    orders = (
        db.query(Order).filter(Order.id.in_(plan_order_ids),
                               Order.location_id.isnot(None)).all()
        if plan_order_ids else []
    )
    order_loc_ids = {o.location_id for o in orders}
    order_locs = {l.id: l for l in db.query(Location).filter(Location.id.in_(order_loc_ids)).all()} if order_loc_ids else {}
    order_markers = []
    for o in orders:
        loc = order_locs.get(o.location_id)
        order_markers.append({
            "order_id": o.id,
            "lat": loc.lat if loc else None, "lng": loc.lng if loc else None,
            "served": o.id in served_order_to_worker,
            "worker_id": served_order_to_worker.get(o.id),
        })

    return MapDataOut(depot=depot_out, driver_routes=driver_routes, order_markers=order_markers)
