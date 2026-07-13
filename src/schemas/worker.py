"""
src/schemas/worker.py

Unified nurse/technician schemas. Which skill enum applies depends on the
company's service_type. A worker row joins to an Employee for identity/contact.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class WorkerOut(BaseModel):
    id: int                                 # nurse/technician row id
    worker_type: str                        # nurse | technician
    employee_id: Optional[int] = None
    name: Optional[str] = None
    contact_number: Optional[str] = None
    contact_email: Optional[str] = None
    skills: list[str] = []
    rating: Optional[float] = None
    orders_completed: Optional[int] = None
    operational_status: Optional[str] = None   # from Employee (availability truth)
    unavailable_reason: Optional[str] = None
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None


class WorkerCreate(BaseModel):
    employee_id: int                        # must reference an existing Employee
    skills: list[str] = []
    rating: Optional[float] = None


class WorkerUpdate(BaseModel):
    skills: Optional[list[str]] = None
    rating: Optional[float] = None
