"""
src/services/alns/runner.py

Solve-lifecycle orchestration: the function a background task runs to take a
RoutePlan from 'optimizing' to 'ready' (or 'failed'), streaming live progress
along the way.

Flow:
  1. load ProblemData for the plan's company/date
  2. run the ALNS solve, forwarding each progress event to the SSE channel
  3. persist the solution + diagnostics into the DB
  4. push a final 'done' event and close the channel

Kept independent of FastAPI: it takes a plain `publish`/`finish` pair of
callables so it can be unit-tested without the web layer.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Callable, Optional

from src.db.database import SessionLocal
from src.core.enums import PlanStatus
from src.services.alns.problem_data import load_problem_data, HaversineProvider, OSMnxProvider
from src.services.alns.solver import solve
from src.services.alns.persistence import persist_solution

logger = logging.getLogger(__name__)


def _resolve_provider(db, force_haversine: bool, publish):
    """
    Pick the travel-time provider.

    Default: OSMnx (real road times + geometry). If the road graph can't be
    loaded at all (download/Redis infra failure) — NOT bad data — fall back to
    Haversine so a demo survives an infra hiccup, and warn loudly. `force_haversine`
    skips OSMnx entirely (dev/testing).
    """
    if force_haversine:
        return HaversineProvider(avg_speed_kmh=40)
    provider = OSMnxProvider(db)
    try:
        provider._get_graph()   # trigger graph load now so infra failure is caught here
        return provider
    except Exception as exc:  # noqa: BLE001 — infra failure only; bad data fails later
        logger.warning(
            f"OSMnx road graph unavailable ({exc}); falling back to Haversine "
            f"straight-line estimates for this solve."
        )
        try:
            publish({"event": "warning",
                     "message": "road network unavailable — using straight-line estimates"})
        except Exception:
            pass
        return HaversineProvider(avg_speed_kmh=40)


def run_solve(
    route_plan_id: int,
    company_id: int,
    planned_date: date,
    repair_mode: str = "proxy",
    config_overrides: Optional[dict] = None,
    order_ids: Optional[list[int]] = None,
    publish: Optional[Callable[[dict], None]] = None,
    finish: Optional[Callable[[Optional[dict]], None]] = None,
    force_haversine: bool = False,
) -> None:
    """
    Execute a full solve for an already-created RoutePlan row (status
    'optimizing'). Runs synchronously in whatever thread the caller provides
    (FastAPI BackgroundTasks). All exceptions are caught and recorded as a
    failed plan — a background task must never crash silently.

    publish(event) / finish(final_event) stream progress; both optional so this
    is callable headless.
    """
    publish = publish or (lambda e: None)
    finish = finish or (lambda e: None)

    db = SessionLocal()
    try:
        from src.db.models import RoutePlan
        plan = db.query(RoutePlan).filter(RoutePlan.id == route_plan_id).one()
        plan.status = PlanStatus.optimizing
        db.commit()

        publish({"event": "loading", "message": "loading road network + problem data"})
        # Real road-network travel times + geometry via OSMnx is the default.
        # Haversine (straight-line) is a FALL-BACK for infrastructure failure
        # only (graph can't load) — NOT for bad data. A location that can't be
        # routed raises LocationUnroutable and hard-fails the solve loudly.
        provider = _resolve_provider(db, force_haversine, publish)
        pd = load_problem_data(db, company_id, planned_date, provider=provider,
                               order_ids=order_ids)

        publish({
            "event": "solving",
            "message": "starting ALNS",
            "orders": len(pd.orders), "workers": len(pd.workers),
            "drivers": len(pd.drivers), "vehicles": len(pd.vehicles),
        })

        result = solve(
            pd, config_overrides=config_overrides, repair_mode=repair_mode,
            progress_cb=publish,
        )

        publish({"event": "persisting", "message": "writing results"})
        persist_solution(db, plan, result.best, result,
                         alns_result=result.raw_result)

        final = {
            "event": "done",
            "route_plan_id": route_plan_id,
            "status": PlanStatus.ready.value,
            "best_objective": round(result.best_objective, 3),
            "initial_objective": round(result.initial_objective, 3),
            "improvement_pct": round(result.improvement_pct, 2),
            "iterations": result.iterations,
            "total_unserved": len(result.best.unassigned),
        }
        finish(final)
        logger.info(f"RoutePlan {route_plan_id} solved: {final}")

    except Exception as exc:  # noqa: BLE001 — background task must not crash
        logger.exception(f"Solve failed for RoutePlan {route_plan_id}")
        try:
            db.rollback()
            from src.db.models import RoutePlan
            plan = db.query(RoutePlan).filter(RoutePlan.id == route_plan_id).one_or_none()
            if plan is not None:
                plan.status = PlanStatus.failed
                db.commit()
        except Exception:
            logger.exception("Failed to mark RoutePlan as failed")
        from src.exceptions.routing import LocationUnroutable
        error_code = "location_unroutable" if isinstance(exc, LocationUnroutable) else "solve_failed"
        finish({"event": "error", "route_plan_id": route_plan_id,
                "error_code": error_code, "message": str(exc)})
    finally:
        db.close()
