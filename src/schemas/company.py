"""src/schemas/company.py"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class CompanyOut(BaseModel):
    id: int
    name: str
    service_type: Optional[str] = None
    contact_number: Optional[str] = None
    contact_email: Optional[str] = None
    timezone: Optional[str] = None
    head_office_location_id: Optional[int] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    contact_number: Optional[str] = None
    contact_email: Optional[str] = None
    timezone: Optional[str] = None
