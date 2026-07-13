"""
src/schemas/mobile.py

Request/response schemas for the mobile field-ops app. Mirrors the app's API
contract (its PLAN.md Section 5). The app talks ONLY to the backend.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


# ── FCM token registration ───────────────────────────────────────────────────

class FcmTokenRequest(BaseModel):
    token: str
    platform: Optional[str] = "android"     # android | ios


# ── my-assignments (the worker's day) ────────────────────────────────────────

class AssignmentStopOut(BaseModel):
    stop_id: int                            # WorkerAssignmentStop id (used for status/complete)
    order_id: int
    plan_id: int
    plan_date: date
    sequence_number: int
    stop_status: str                        # WorkerStopStatus value
    order_name: Optional[str] = None
    customer_name: Optional[str] = None
    address_text: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    required_skills: list[str] = []
    service_duration_min: Optional[int] = None
    service_start_estimated: Optional[datetime] = None
    service_end_estimated: Optional[datetime] = None
    timewindow_start: Optional[datetime] = None
    timewindow_end: Optional[datetime] = None
    actual_service_start: Optional[datetime] = None
    actual_service_end: Optional[datetime] = None
    route_polyline: Optional[dict] = None   # GeoJSON LineString (from driver route), best-effort


# ── status / complete ────────────────────────────────────────────────────────

class StopStatusRequest(BaseModel):
    status: str                             # en_route | arrived | in_progress


class StopCompleteRequest(BaseModel):
    notes: Optional[str] = None
    # optional client-reported completion time; server uses now() if absent
    completed_at: Optional[datetime] = None


class StopOut(BaseModel):
    stop_id: int
    order_id: int
    stop_status: str
    actual_service_start: Optional[datetime] = None
    actual_service_end: Optional[datetime] = None
    order_status: str                       # rolled-up Order.status


# ── position ping ────────────────────────────────────────────────────────────

class PositionPing(BaseModel):
    lat: float
    lng: float
    recorded_at: Optional[datetime] = None
    accuracy_m: Optional[float] = None


class PositionBatchRequest(BaseModel):
    pings: list[PositionPing]


class PositionBatchResponse(BaseModel):
    recorded: int


# ── availability ─────────────────────────────────────────────────────────────

class AvailabilityRequest(BaseModel):
    available: bool
    reason: Optional[str] = None            # required-ish when going unavailable


class AvailabilityOut(BaseModel):
    employee_id: int
    available: bool
    operational_status: str
    reason: Optional[str] = None
    since: Optional[datetime] = None
