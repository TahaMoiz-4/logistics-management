# from sqlalchemy import (
#     Column, Numeric, DateTime, ForeignKey
# )
# from sqlalchemy.dialects.postgresql import UUID
# from sqlalchemy.orm import relationship
# from sqlalchemy.sql import func
# from src.db.models.base import Base, gen_uuid

# class DeliveryWindow(Base):
#     __tablename__ = "delivery_windows"
 
#     id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
#     order_id        = Column(UUID(as_uuid=False), ForeignKey("orders.id"), nullable=False, unique=True)
#     earliest        = Column(DateTime(timezone=True), nullable=False)
#     latest          = Column(DateTime(timezone=True), nullable=False)
#     # cost per minute of lateness — enables soft time-window VRP
#     penalty_per_min = Column(Numeric(10, 4), default=0)
 
#     order = relationship("Order", back_populates="delivery_window")
 
#     def __repr__(self):
#         return f"<DeliveryWindow order={self.order_id} {self.earliest}→{self.latest}>"
