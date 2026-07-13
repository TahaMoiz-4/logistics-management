"""src/schemas/tracking.py — live position + availability roster schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LivePosition(BaseModel):
    subject_type: str                  # nurse | technician | driver | vehicle
    subject_id: int                    # the nurse/technician/driver/vehicle row id
    name: Optional[str] = None
    lat: float
    lng: float
    recorded_at: Optional[datetime] = None
    # contact info so a map click-popup is self-contained (no second call)
    employee_id: Optional[int] = None
    employee_code: Optional[str] = None      # human code, e.g. "EMP-42"
    contact_number: Optional[str] = None
    # recency: how old this ping is, and whether it's past the stale threshold
    seconds_ago: Optional[int] = None
    is_stale: bool = False


class LiveTrackingOut(BaseModel):
    positions: list[LivePosition]
    as_of: datetime
    stale_after_sec: int               # positions older than this are is_stale=true


class AvailabilityRosterEntry(BaseModel):
    employee_id: int
    name: str
    role: Optional[str] = None          # nurse | technician | driver
    contact_number: Optional[str] = None
    contact_email: Optional[str] = None
    operational_status: str             # active | suspended | inactive
    available: bool
    unavailable_reason: Optional[str] = None
    since: Optional[datetime] = None
