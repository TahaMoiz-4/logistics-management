"""src/db/repositories/order.py"""

from datetime import date
from typing import Optional, Sequence

from src.db.models import Order
from src.core.enums import OrderStatus
from src.db.repositories.base import BaseRepository

SERVABLE_STATUSES = (OrderStatus.pending, OrderStatus.assigned)


class OrderRepository(BaseRepository[Order]):
    model = Order

    def list_servable(
        self, company_id: int, from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> list[Order]:
        q = self._base_query(company_id).filter(
            Order.status.in_(SERVABLE_STATUSES),
            Order.location_id.isnot(None),
        )
        if from_date is not None:
            q = q.filter((Order.service_date.is_(None)) | (Order.service_date >= from_date))
        if to_date is not None:
            q = q.filter((Order.service_date.is_(None)) | (Order.service_date <= to_date))
        return q.order_by(Order.service_date.asc().nullslast(), Order.id.asc()).all()

    def get_many(self, ids: Sequence[int]) -> list[Order]:
        return self.db.query(Order).filter(Order.id.in_(list(ids))).all()

    def count_servable_on(self, company_id: int, on_date: date) -> int:
        return (
            self._base_query(company_id)
            .filter(
                Order.status.in_(SERVABLE_STATUSES),
                Order.service_date == on_date,
                Order.location_id.isnot(None),
            )
            .count()
        )
