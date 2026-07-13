"""
src/db/repositories/sys_users.py

DB access for SysUsers (system operators / web admins) and their company link.
"""

from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import SysUsers, UserCompany


class SysUserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> Optional[SysUsers]:
        return (
            self.db.query(SysUsers)
            .filter(SysUsers.id == user_id, SysUsers.deleted_at.is_(None))
            .first()
        )

    def get_by_username(self, username: str) -> Optional[SysUsers]:
        return (
            self.db.query(SysUsers)
            .filter(SysUsers.username == username, SysUsers.deleted_at.is_(None))
            .first()
        )

    def company_id_for(self, user_id: int) -> Optional[int]:
        """Resolve the (first) company this operator belongs to via UserCompany."""
        link = (
            self.db.query(UserCompany)
            .filter(UserCompany.user_id == user_id, UserCompany.deleted_at.is_(None))
            .order_by(UserCompany.company_id)
            .first()
        )
        return link.company_id if link else None
