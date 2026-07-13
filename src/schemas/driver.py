"""src/schemas/driver.py"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class DriverOut(BaseModel):
    id: int
    company_id: int
    employee_id: Optional[int] = None
    name: Optional[str] = None
    contact_number: Optional[str] = None
    contact_email: Optional[str] = None
    drivers_license_number: Optional[str] = None
    skills: list[str] = []                  # VehicleType values the driver may operate
    rating: Optional[float] = None
    kms_driven: Optional[float] = None
    orders_completed: Optional[int] = None
    operational_status: Optional[str] = None
    unavailable_reason: Optional[str] = None
    vehicle_id: Optional[int] = None
    vehicle_plate: Optional[str] = None


class DriverCreate(BaseModel):
    employee_id: int
    vehicle_id: Optional[int] = None
    drivers_license_number: Optional[str] = None
    skills: list[str] = []                  # VehicleType values


class DriverUpdate(BaseModel):
    vehicle_id: Optional[int] = None
    drivers_license_number: Optional[str] = None
    skills: Optional[list[str]] = None
