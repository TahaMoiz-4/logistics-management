"""
src/schemas/auth.py

Request/response schemas for web (SysUser) and mobile (Employee) auth.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ── requests ─────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


# ── web (SysUser) ────────────────────────────────────────────────────────────

class SysUserOut(BaseModel):
    id: int
    username: str
    role: str
    company_id: int
    contact_email: Optional[str] = None
    contact_number: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    user: SysUserOut


# ── mobile (Employee/worker) ─────────────────────────────────────────────────

class WorkerOut(BaseModel):
    employee_id: int
    name: str
    company_id: int
    role: Optional[str] = None          # nurse | technician | driver
    contact_number: Optional[str] = None
    contact_email: Optional[str] = None
    operational_status: str
    shift_start: Optional[str] = None    # "HH:MM"
    shift_end: Optional[str] = None


class WorkerLoginResponse(BaseModel):
    token: str
    worker: WorkerOut
