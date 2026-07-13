"""src/schemas/order.py — full order CRUD schemas (extends the ServableOrderOut in route_plan.py)."""

from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class OrderOut(BaseModel):
    id: int
    name: Optional[str] = None
    company_id: int
    customer_id: int
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    location_id: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address_text: Optional[str] = None
    status: str
    priority: str
    service_date: Optional[date] = None
    timewindow_start: Optional[datetime] = None
    timewindow_end: Optional[datetime] = None
    service_duration_min: Optional[int] = None
    required_nurse_skills: list[str] = []
    required_tech_skills: list[str] = []
    weight_kg: Optional[float] = None
    volume_m3: Optional[float] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class OrderCreate(BaseModel):
    customer_id: int
    service_date: date
    # location: either an existing location_id, or lat/lng to create one
    location_id: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address_text: Optional[str] = None
    name: Optional[str] = None
    priority: Optional[str] = None          # OrderPriority value
    timewindow_start: Optional[datetime] = None
    timewindow_end: Optional[datetime] = None
    service_duration_min: Optional[int] = None
    required_skills: list[str] = []         # matched against company service_type
    weight_kg: Optional[float] = None
    volume_m3: Optional[float] = None
    notes: Optional[str] = None


class OrderUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    service_date: Optional[date] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address_text: Optional[str] = None
    timewindow_start: Optional[datetime] = None
    timewindow_end: Optional[datetime] = None
    service_duration_min: Optional[int] = None
    required_skills: Optional[list[str]] = None
    weight_kg: Optional[float] = None
    volume_m3: Optional[float] = None
    notes: Optional[str] = None
