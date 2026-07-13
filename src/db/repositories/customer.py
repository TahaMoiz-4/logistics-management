"""src/db/repositories/customer.py"""

from src.db.models import Customer
from src.db.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    model = Customer

    def order_count(self, customer_id: int) -> int:
        from src.db.models import Order
        return (
            self.db.query(Order)
            .filter(Order.customer_id == customer_id, Order.deleted_at.is_(None))
            .count()
        )
