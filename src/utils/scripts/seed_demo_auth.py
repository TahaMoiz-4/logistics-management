"""
src/utils/scripts/seed_demo_auth.py

Seed demo login accounts so both web and mobile auth work out of the box.

Creates (idempotently):
  * company 1 (nurse) + company 2 (technician) if missing
  * SysUser 'admin1' -> company 1, 'admin2' -> company 2   (web login)
  * each existing Employee gets a username 'worker<emp_id>' + password  (mobile login)

Demo password for everyone: "password"

Usage:
    python -m src.utils.scripts.seed_demo_auth
"""

from __future__ import annotations

from src.db.database import SessionLocal
from src.db.models import Company, SysUsers, UserCompany, Employee
from src.core.enums import ServiceType
from src.core.security import hash_password

DEMO_PASSWORD = "password"


def _ensure_company(db, company_id: int, name: str, service_type: ServiceType) -> Company:
    c = db.query(Company).filter(Company.id == company_id).one_or_none()
    if c is None:
        c = Company(id=company_id, name=name, service_type=service_type, created_by=1)
        db.add(c); db.flush()
        print(f"  created company {company_id} ({service_type.value})")
    elif c.service_type is None:
        c.service_type = service_type
        print(f"  set company {company_id} service_type={service_type.value}")
    return c


def _ensure_sysuser(db, username: str, company_id: int) -> SysUsers:
    u = db.query(SysUsers).filter(SysUsers.username == username).one_or_none()
    if u is None:
        u = SysUsers(username=username, password_hash=hash_password(DEMO_PASSWORD),
                    role="admin", created_by=1)
        db.add(u); db.flush()
        print(f"  created sysuser '{username}' (id={u.id})")
    else:
        u.password_hash = hash_password(DEMO_PASSWORD)
    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == u.id, UserCompany.company_id == company_id)
        .one_or_none()
    )
    if link is None:
        db.add(UserCompany(user_id=u.id, company_id=company_id, created_by=1))
        print(f"  linked sysuser '{username}' -> company {company_id}")
    return u


def _ensure_employee_logins(db) -> int:
    """Give every employee a username/password for mobile login."""
    n = 0
    for emp in db.query(Employee).filter(Employee.deleted_at.is_(None)).all():
        if not emp.username:
            emp.username = f"worker{emp.id}"
            emp.password_hash = hash_password(DEMO_PASSWORD)
            n += 1
    return n


def main():
    db = SessionLocal()
    try:
        print("Seeding demo auth...")
        _ensure_company(db, 1, "Demo Nurse Co", ServiceType.nurse)
        _ensure_company(db, 2, "Demo Tech Co", ServiceType.technician)
        _ensure_sysuser(db, "admin1", 1)
        _ensure_sysuser(db, "admin2", 2)
        n = _ensure_employee_logins(db)
        db.commit()
        print(f"  gave {n} employees mobile logins (username 'worker<id>')")
        print(f"Done. Demo password for all accounts: '{DEMO_PASSWORD}'")
        print("  web:    admin1 / admin2")
        print("  mobile: worker<employee_id>")
    finally:
        db.close()


if __name__ == "__main__":
    main()
