"""src/schemas/vehicle.py"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class VehicleOut(BaseModel):
    id: int
    company_id: int
    depot_id: int
    depot_name: Optional[str] = None
    license_plate: str
    type: str
    model: Optional[str] = None
    color: Optional[str] = None
    engine_cc: Optional[int] = None
    max_weight_kg: Optional[float] = None
    max_volume_m3: Optional[float] = None
    seating_capacity: Optional[int] = None
    avg_speed_kmh: Optional[float] = None
    fuel_type: Optional[str] = None
    fuel_average: Optional[float] = None
    monthly_maintenance_cost: Optional[float] = None
    operational_status: Optional[str] = None
    assigned_driver_id: Optional[int] = None


class VehicleCreate(BaseModel):
    depot_id: int
    license_plate: str
    type: str                      # VehicleType value
    model: Optional[str] = None
    color: Optional[str] = None
    engine_cc: Optional[int] = None
    max_weight_kg: Optional[float] = None
    max_volume_m3: Optional[float] = None
    seating_capacity: Optional[int] = None
    avg_speed_kmh: Optional[float] = None
    fuel_type: Optional[str] = None
    fuel_average: Optional[float] = None
    monthly_maintenance_cost: Optional[float] = None


class VehicleUpdate(BaseModel):
    depot_id: Optional[int] = None
    license_plate: Optional[str] = None
    type: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    engine_cc: Optional[int] = None
    max_weight_kg: Optional[float] = None
    max_volume_m3: Optional[float] = None
    seating_capacity: Optional[int] = None
    avg_speed_kmh: Optional[float] = None
    fuel_type: Optional[str] = None
    fuel_average: Optional[float] = None
    monthly_maintenance_cost: Optional[float] = None
    operational_status: Optional[str] = None
