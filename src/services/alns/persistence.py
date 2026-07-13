"""
src/services/alns/persistence.py

Turns a solved RoutingState into (1) persisted DB rows across the four
route/assignment tables and (2) a rich solver-diagnostics JSON blob for the
demo dashboard.

The diagnostics blob is deliberately detailed — it's what the frontend's
"solver internals" view renders: the per-iteration objective trace (the cost
graph), adaptive operator counts, final cost breakdown, timing, and the
unserved-order reasons.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.core.enums import PlanStatus, RouteStatus, StopType, ServiceType
from src.services.alns.state import RoutingState


# ---------------------------------------------------------------------------
# Diagnostics blob
# ---------------------------------------------------------------------------

def _unserved_reason(state: RoutingState, order_id: int) -> str:
    """Best-effort classification of why an order is unassigned."""
    pd = state.problem_data
    feasible = [w for w in pd.workers if pd.worker_can_serve(w.id, order_id)]
    if not feasible:
        return "no_feasible_skill"
    return "no_capacity_or_time_fit"


def build_diagnostics(state: RoutingState, result, alns_result=None) -> dict:
    """
    Assemble the full diagnostics JSON.

    Args:
        state:  the best RoutingState
        result: SolveResult (from solver.solve)
        alns_result: raw alns.Result — provides statistics (iteration trace,
                     operator counts). Optional so this is testable standalone.
    """
    pd = state.problem_data

    diag: dict = {
        "summary": {
            "initial_objective": round(result.initial_objective, 3),
            "best_objective": round(result.best_objective, 3),
            "improvement_pct": round(result.improvement_pct, 2),
            "iterations": result.iterations,
            "runtime_sec": round(result.runtime_sec, 3),
            "iters_per_sec": round(result.iterations / result.runtime_sec, 1)
            if result.runtime_sec else 0,
            "total_orders": len(pd.orders),
            "total_assigned": sum(len(s) for s in state.worker_routes.values()),
            "total_unserved": len(state.unassigned),
            "workers_used": sum(1 for s in state.worker_routes.values() if s),
            "workers_idle": sum(1 for s in state.worker_routes.values() if not s),
        },
        "cost_breakdown": {k: round(v, 3) for k, v in result.breakdown.items()},
        "penalties_used": dict(state.penalties),
        "unserved": [
            {"order_id": oid, "reason": _unserved_reason(state, oid)}
            for oid in state.unassigned
        ],
    }

    # per-iteration trace + adaptive operator stats from the alns run
    if alns_result is not None:
        stats = alns_result.statistics
        objectives = [round(float(o), 3) for o in stats.objectives]
        diag["iteration_trace"] = {
            # objective at each iteration — THE cost graph for the dashboard
            "objectives": objectives,
            "runtimes": [round(float(r), 5) for r in stats.runtimes],
            "num_iterations": len(objectives),
            # running best, so the frontend can draw the monotone best-so-far line
            "best_so_far": _running_min(objectives),
        }
        diag["operator_stats"] = {
            "destroy": _op_counts(stats.destroy_operator_counts),
            "repair": _op_counts(stats.repair_operator_counts),
            # the 4 outcome buckets these counts correspond to
            "outcome_legend": ["new_best", "better", "accepted", "rejected"],
        }

    return diag


def _running_min(values: list[float]) -> list[float]:
    out, m = [], float("inf")
    for v in values:
        m = min(m, v)
        out.append(round(m, 3))
    return out


def _op_counts(counts: dict) -> dict:
    """alns stores per-operator [new_best, better, accepted, rejected] tallies."""
    result = {}
    for name, arr in counts.items():
        arr = [int(x) for x in arr]
        result[name] = {
            "counts": arr,
            "total_used": sum(arr),
            "new_best": arr[0] if len(arr) > 0 else 0,
            "better": arr[1] if len(arr) > 1 else 0,
            "accepted": arr[2] if len(arr) > 2 else 0,
            "rejected": arr[3] if len(arr) > 3 else 0,
        }
    return result


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

def _sec_to_dt(planned: date, sec: float) -> datetime:
    """Seconds-since-midnight -> tz-aware datetime on the planned date."""
    base = datetime.combine(planned, time(0, 0), tzinfo=timezone.utc)
    return base + timedelta(seconds=float(sec))


def _stitch_geometry(leg_geometries: list[dict]) -> Optional[dict]:
    """
    Combine per-leg GeoJSON geometries (in driver-route order) into one
    MultiLineString for the whole route — one segment per leg. Each leg may be a
    LineString or a MultiLineString (osmnx dissolve can yield either); both are
    normalized to lists of coordinate paths. Returns None if nothing to draw
    (Haversine mode). Coordinates are GeoJSON [lng, lat] order.
    """
    segments: list = []
    for g in leg_geometries or []:
        if not g:
            continue
        gtype = g.get("type")
        if gtype == "LineString":
            coords = g.get("coordinates", [])
            if coords:
                segments.append(coords)
        elif gtype == "MultiLineString":
            for part in g.get("coordinates", []):
                if part:
                    segments.append(part)
    if not segments:
        return None
    return {"type": "MultiLineString", "coordinates": segments}


def persist_solution(db: Session, route_plan, state: RoutingState, result,
                     alns_result=None, created_by: int = 1) -> None:
    """
    Write the solved schedule into DriverRoute / DriverRouteStop /
    WorkerAssignment / WorkerAssignmentStop rows, and stamp the RoutePlan with
    result summary + diagnostics. Commits.

    Idempotency: caller is responsible for a fresh plan; this appends rows.
    """
    from src.db.models import (
        DriverRoute, DriverRouteStop, WorkerAssignment, WorkerAssignmentStop,
    )

    pd = state.problem_data
    planned = route_plan.planned_date
    sched = state.derive_driver_routes()
    geo = pd.geometry_source   # OSMnxProvider with leg_geometry(), or None (Haversine)

    # ---- worker assignments + their service stops --------------------------
    # Track each worker stop by the node it's served at, so we can link its
    # dropoff_stop_id to the driver stop that delivered the worker there.
    node_to_location = {n.index: n.location_id for n in pd.nodes}
    order_to_node = {o.id: o.node_index for o in pd.orders}
    # key each worker's service stop by (worker_id, node) so a pooled driver leg
    # can link EACH of its riders to their own stop (riders may sit at different
    # nodes within the shared pool zone).
    worker_stops: dict[tuple[int, int], object] = {}
    for worker_id, visits in sched.visits_by_worker.items():
        if not visits:
            continue
        wa = WorkerAssignment(
            plan_id=route_plan.id, worker_id=worker_id,
            worker_type=pd.service_type, created_by=created_by,
        )
        db.add(wa); db.flush()
        for v in visits:
            was = WorkerAssignmentStop(
                worker_assignment_id=wa.id, order_id=v.order_id,
                sequence_number=v.seq,
                service_start_estimated=_sec_to_dt(planned, v.service_start_sec),
                service_end_estimated=_sec_to_dt(planned, v.service_end_sec),
                created_by=created_by,
            )
            db.add(was); db.flush()
            node = order_to_node.get(v.order_id)
            if node is not None:
                worker_stops[(worker_id, node)] = was

    # ---- driver routes + their legs ----------------------------------------
    legs_by_driver: dict[int, list] = {}
    for leg in sched.legs:
        legs_by_driver.setdefault(leg.driver_id, []).append(leg)

    total_distance_all = 0
    for driver_id, legs in legs_by_driver.items():
        legs.sort(key=lambda l: l.depart_sec)
        vehicle_id = legs[0].vehicle_id
        dr = DriverRoute(
            plan_id=route_plan.id, driver_id=driver_id, vehicle_id=vehicle_id,
            status=RouteStatus.pending, created_by=created_by,
        )
        db.add(dr); db.flush()

        seq = 0
        total_dist = 0
        total_time = 0
        leg_geometries: list[dict] = []
        # depot start
        db.add(DriverRouteStop(
            driver_route_id=dr.id, location_id=node_to_location[pd.depot_node_index],
            sequence_number=seq, stop_type=StopType.depot_start,
            eta=_sec_to_dt(planned, legs[0].depart_sec), created_by=created_by,
        ))
        seq += 1
        for leg in legs:
            dist = int(pd.distance(leg.from_node, leg.to_node))
            total_dist += dist
            total_time += int(leg.arrive_sec - leg.depart_sec)
            dstop = DriverRouteStop(
                driver_route_id=dr.id, location_id=node_to_location[leg.to_node],
                sequence_number=seq, stop_type=StopType.dropoff,
                eta=_sec_to_dt(planned, leg.arrive_sec),
                etd=_sec_to_dt(planned, leg.arrive_sec),
                distance_from_prev_m=dist,
                time_from_prev_sec=int(leg.arrive_sec - leg.depart_sec),
                created_by=created_by,
            )
            db.add(dstop); db.flush()
            # link each rider on this (possibly pooled) leg to their own service
            # stop via their actual destination node.
            rider_nodes = leg.rider_to_nodes or {w: leg.to_node for w in leg.rider_worker_ids}
            for worker_id, dest_node in rider_nodes.items():
                was = worker_stops.get((worker_id, dest_node))
                if was is not None and was.dropoff_stop_id is None:
                    was.dropoff_stop_id = dstop.id
            # collect real road geometry for this leg (if OSMnx routed it)
            if geo is not None:
                g = geo.leg_geometry(leg.from_node, leg.to_node)
                if g:
                    leg_geometries.append(g)
            seq += 1
        # depot end
        db.add(DriverRouteStop(
            driver_route_id=dr.id, location_id=node_to_location[pd.depot_node_index],
            sequence_number=seq, stop_type=StopType.depot_end,
            eta=_sec_to_dt(planned, legs[-1].arrive_sec), created_by=created_by,
        ))
        dr.total_distance_m = total_dist
        dr.total_time_sec = total_time
        dr.geometry = _stitch_geometry(leg_geometries)
        total_distance_all += total_dist

    # ---- stamp the plan ----------------------------------------------------
    route_plan.status = PlanStatus.ready
    route_plan.objective_value = float(result.best_objective)
    route_plan.total_orders = len(pd.orders)
    route_plan.total_unserved = len(state.unassigned)
    route_plan.total_routes = len(legs_by_driver)
    route_plan.solver_diagnostics = build_diagnostics(state, result, alns_result)
    route_plan.optimized_at = datetime.now(timezone.utc)

    db.commit()
