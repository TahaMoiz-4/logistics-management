"""src/db/repositories/company.py — Company reads/updates (no create/delete: tenant-fixed)."""

from typing import Optional
from sqlalchemy.orm import Session
from src.db.models import Company


class CompanyRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, company_id: int) -> Optional[Company]:
        return (
            self.db.query(Company)
            .filter(Company.id == company_id, Company.deleted_at.is_(None))
            .first()
        )

    def update(self, company: Company, data: dict, actor_id: int) -> Company:
        for k, v in data.items():
            if v is not None and hasattr(company, k):
                setattr(company, k, v)
        company.updated_by = actor_id
        self.db.commit()
        self.db.refresh(company)
        return company
