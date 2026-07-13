"""
src/schemas/route_plan.py

Pydantic response schemas for the route-plan API. Deliberately detailed — the
demo frontend renders solver internals (iteration trace, operator stats, cost
breakdown) alongside the routes themselves.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class CreateRoutePlanRequest(BaseModel):
    # company_id comes from the authenticated user, NOT the request body.
    depot_id: Optional[int] = None          # defaults to the company's first depot
    # Provide order_ids (the user's selection) and/or planned_date:
    #   * order_ids given  -> planned_date is DERIVED from them (all must share
    #     one service_date); if planned_date is also passed it must match.
    #   * order_ids omitted -> planned_date is REQUIRED; solves all servable
    #     (pending/assigned) orders on that date.
    order_ids: Optional[list[int]] = None
    planned_date: Optional[date] = None
    name: Optional[str] = None
    repair_mode: str = "proxy"              # "proxy" | "shuttle_aware"
    config_overrides: Optional[dict] = None  # merged into ALNS_CONFIG for this run


class CreateRoutePlanResponse(BaseModel):
    route_plan_id: int
    status: str
    planned_date: date                       # resolved date the plan solves
    order_count: int                         # how many orders entered the solve
    stream_url: str                          # SSE endpoint to watch live progress


# ---------------------------------------------------------------------------
# Order selection list (for the "pick orders" page)
# ---------------------------------------------------------------------------

class ServableOrderOut(BaseModel):
    id: int
    name: Optional[str] = None
    customer_id: int
    service_date: Optional[date] = None
    status: str
    priority: str
    required_skills: list[str]               # from whichever skill column applies
    timewindow_start: Optional[datetime] = None
    timewindow_end: Optional[datetime] = None
    service_duration_min: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address_text: Optional[str] = None


# ---------------------------------------------------------------------------
# Result summary
# ---------------------------------------------------------------------------

class RoutePlanSummary(BaseModel):
    id: int
    company_id: int
    depot_id: int
    planned_date: date
    status: str
    name: Optional[str] = None
    objective_value: Optional[float] = None
    total_orders: Optional[int] = None
    total_routes: Optional[int] = None
    total_unserved: Optional[int] = None
    optimized_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ApproveResponse(BaseModel):
    route_plan_id: int
    status: str
    orders_marked_assigned: int
    workers_notified: int
    notify_mode: str            # real | stub | none


# ---------------------------------------------------------------------------
# Driver routes (one row per driver's day)
# ---------------------------------------------------------------------------

class DriverStopOut(BaseModel):
    sequence_number: int
    stop_type: str
    location_id: int
    lat: Optional[float] = None
    lng: Optional[float] = None
    eta: Optional[datetime] = None
    etd: Optional[datetime] = None
    distance_from_prev_m: Optional[int] = None
    time_from_prev_sec: Optional[int] = None


class DriverRouteOut(BaseModel):
    id: int
    driver_id: Optional[int] = None
    vehicle_id: int
    status: str
    total_distance_m: Optional[int] = None
    total_time_sec: Optional[int] = None
    stops: list[DriverStopOut]


# ---------------------------------------------------------------------------
# Worker assignments (one row per nurse/tech's day)
# ---------------------------------------------------------------------------

class WorkerStopOut(BaseModel):
    sequence_number: int
    order_id: int
    lat: Optional[float] = None
    lng: Optional[float] = None
    service_start_estimated: Optional[datetime] = None
    service_end_estimated: Optional[datetime] = None


class WorkerAssignmentOut(BaseModel):
    id: int
    worker_id: int
    worker_type: str
    stops: list[WorkerStopOut]


# ---------------------------------------------------------------------------
# Unserved orders
# ---------------------------------------------------------------------------

class UnservedOrderOut(BaseModel):
    order_id: int
    reason: str


# ---------------------------------------------------------------------------
# Diagnostics (the demo dashboard payload) — passthrough of the stored JSON,
# typed loosely since it's rich and evolving.
# ---------------------------------------------------------------------------

class DiagnosticsOut(BaseModel):
    summary: dict
    cost_breakdown: dict
    penalties_used: dict
    unserved: list[dict]
    iteration_trace: Optional[dict] = None
    operator_stats: Optional[dict] = None


# ---------------------------------------------------------------------------
# Map data (GeoJSON-ish for the spatial view)
# ---------------------------------------------------------------------------

class MapDataOut(BaseModel):
    depot: dict                              # {lat, lng, location_id}
    driver_routes: list[dict]                # [{driver_id, vehicle_id, points:[{lat,lng,seq,stop_type}]}]
    order_markers: list[dict]                # [{order_id, lat, lng, served, worker_id?}]
