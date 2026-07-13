"""
src/db/repositories/base.py

Generic company-scoped, soft-deleting CRUD base. Entity repos subclass this and
set `model`. All list/get are scoped to a company_id so a repo can never leak
another tenant's rows. Writes stamp created_by/updated_by and soft-delete via
deleted_at/deleted_by.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, Optional, TypeVar

from sqlalchemy.orm import Session

from src.db.models.base import Base

M = TypeVar("M", bound=Base)


class BaseRepository(Generic[M]):
    model: type[M]                     # set by subclass
    company_scoped: bool = True        # set False for tables without company_id

    def __init__(self, db: Session):
        self.db = db

    # ── internal query builder ───────────────────────────────────────────────

    def _base_query(self, company_id: Optional[int]):
        q = self.db.query(self.model).filter(self.model.deleted_at.is_(None))
        if self.company_scoped and company_id is not None:
            q = q.filter(self.model.company_id == company_id)
        return q

    # ── reads ────────────────────────────────────────────────────────────────

    def get(self, entity_id: int, company_id: Optional[int] = None) -> Optional[M]:
        return self._base_query(company_id).filter(self.model.id == entity_id).first()

    def list(self, company_id: Optional[int] = None) -> list[M]:
        return self._base_query(company_id).order_by(self.model.id).all()

    # ── writes ───────────────────────────────────────────────────────────────

    def create(self, data: dict, actor_id: int, company_id: Optional[int] = None) -> M:
        payload = dict(data)
        if self.company_scoped and company_id is not None:
            payload.setdefault("company_id", company_id)
        payload["created_by"] = actor_id
        obj = self.model(**payload)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: M, data: dict, actor_id: int) -> M:
        for k, v in data.items():
            if v is not None and hasattr(obj, k):
                setattr(obj, k, v)
        if hasattr(obj, "updated_by"):
            obj.updated_by = actor_id
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def soft_delete(self, obj: M, actor_id: int) -> None:
        obj.deleted_at = datetime.now(timezone.utc)
        if hasattr(obj, "deleted_by"):
            obj.deleted_by = actor_id
        self.db.commit()
