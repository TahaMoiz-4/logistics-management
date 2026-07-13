"""src/schemas/depot.py"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class DepotOut(BaseModel):
    id: int
    name: str
    company_id: int
    operational_status: Optional[str] = None
    location_id: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address_text: Optional[str] = None


class DepotCreate(BaseModel):
    name: str
    lat: float
    lng: float
    address_text: Optional[str] = None


class DepotUpdate(BaseModel):
    name: Optional[str] = None
    operational_status: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address_text: Optional[str] = None
