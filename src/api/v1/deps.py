"""
src/api/v1/deps.py

Auth dependencies. Two identities:
  * CurrentUser   — a web operator (SysUser), via get_current_user
  * CurrentWorker — a mobile field worker (Employee), via get_current_worker

Both parse the Bearer token, verify its signature, confirm the subject type,
and load the subject. company_id ALWAYS comes from here, never from the request,
so endpoints can't be tricked into cross-tenant access.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.core.security import verify_token, SUBJECT_SYSUSER, SUBJECT_EMPLOYEE
from src.db.repositories.sys_users import SysUserRepository
from src.db.repositories.employee import EmployeeRepository
from src.exceptions.auth import InvalidToken, NotAuthenticated


@dataclass
class CurrentUser:
    user_id: int
    company_id: int
    role: str
    username: str


@dataclass
class CurrentWorker:
    employee_id: int
    company_id: int
    role: Optional[str]     # nurse | technician | driver
    name: str


def _extract_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise NotAuthenticated()
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise InvalidToken()
    return parts[1]


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    payload = verify_token(_extract_token(authorization))
    if not payload or payload.get("typ") != SUBJECT_SYSUSER:
        raise InvalidToken()
    repo = SysUserRepository(db)
    user = repo.get(payload["sub"])
    if user is None:
        raise InvalidToken()
    return CurrentUser(
        user_id=user.id, company_id=payload["cid"],
        role=user.role, username=user.username,
    )


def get_current_worker(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> CurrentWorker:
    payload = verify_token(_extract_token(authorization))
    if not payload or payload.get("typ") != SUBJECT_EMPLOYEE:
        raise InvalidToken()
    repo = EmployeeRepository(db)
    emp = repo.get(payload["sub"])
    if emp is None:
        raise InvalidToken()
    return CurrentWorker(
        employee_id=emp.id, company_id=payload["cid"],
        role=repo.role_for(emp.id), name=emp.name,
    )
