"""src/schemas/employee.py"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class EmployeeOut(BaseModel):
    id: int
    name: str
    company_id: int
    contact_number: Optional[str] = None
    contact_email: Optional[str] = None
    cnic: Optional[str] = None
    shift_start: Optional[str] = None      # "HH:MM"
    shift_end: Optional[str] = None
    operational_status: Optional[str] = None
    unavailable_reason: Optional[str] = None
    role: Optional[str] = None             # nurse|technician|driver (derived)
    has_login: bool = False                # username set?


class EmployeeCreate(BaseModel):
    name: str
    contact_number: Optional[str] = None
    contact_email: Optional[str] = None
    cnic: Optional[str] = None
    shift_start: Optional[str] = None      # "HH:MM"
    shift_end: Optional[str] = None
    # optional mobile login credentials
    username: Optional[str] = None
    password: Optional[str] = None


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    contact_number: Optional[str] = None
    contact_email: Optional[str] = None
    cnic: Optional[str] = None
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None
    operational_status: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
