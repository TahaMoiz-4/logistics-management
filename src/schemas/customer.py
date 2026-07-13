"""src/schemas/customer.py"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class CustomerOut(BaseModel):
    id: int
    name: str
    company_id: int
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    location_id: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address_text: Optional[str] = None
    order_count: int = 0


class CustomerCreate(BaseModel):
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    # optional location — if lat/lng given, a Location row is created
    lat: Optional[float] = None
    lng: Optional[float] = None
    address_text: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address_text: Optional[str] = None
