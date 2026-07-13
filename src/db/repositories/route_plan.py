"""src/db/repositories/route_plan.py — RoutePlan history reads + lifecycle helpers."""

from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import RoutePlan
from src.db.repositories.base import BaseRepository


class RoutePlanRepository(BaseRepository[RoutePlan]):
    model = RoutePlan

    def list_for_company(self, company_id: int) -> list[RoutePlan]:
        return (
            self.db.query(RoutePlan)
            .filter(RoutePlan.company_id == company_id, RoutePlan.deleted_at.is_(None))
            .order_by(RoutePlan.planned_date.desc(), RoutePlan.id.desc())
            .all()
        )

    def get_scoped(self, plan_id: int, company_id: int) -> Optional[RoutePlan]:
        return (
            self.db.query(RoutePlan)
            .filter(RoutePlan.id == plan_id, RoutePlan.company_id == company_id,
                    RoutePlan.deleted_at.is_(None))
            .first()
        )
