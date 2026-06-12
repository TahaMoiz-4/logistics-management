import uuid
import enum
from datetime import datetime
 
from sqlalchemy import (
    Column, String, Float, Integer, Numeric, Boolean,
    Text, DateTime, Date, Time, ForeignKey, Enum, JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid
from src.core.enums import OrderPriority, OrderStatus

class Order(Base):
    __tablename__ = "orders"
 
    id                  = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id          = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)
    customer_id         = Column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    # null pickup = starts from depot
    pickup_location_id  = Column(UUID(as_uuid=False), ForeignKey("locations.id"), nullable=True)
    dropoff_location_id = Column(UUID(as_uuid=False), ForeignKey("locations.id"), nullable=False)
    weight_kg           = Column(Numeric(10, 3), nullable=False)
    volume_m3           = Column(Numeric(10, 4))
    priority            = Column(Enum(OrderPriority), default=OrderPriority.normal)
    status              = Column(Enum(OrderStatus),   default=OrderStatus.pending)
    notes               = Column(Text)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
 
    company          = relationship("Company",  back_populates="orders")
    customer         = relationship("Customer", back_populates="orders")
    pickup_location  = relationship("Location", foreign_keys=[pickup_location_id],  back_populates="pickup_orders")
    dropoff_location = relationship("Location", foreign_keys=[dropoff_location_id], back_populates="dropoff_orders")
    delivery_window  = relationship("DeliveryWindow", back_populates="order", uselist=False)
    route_stops      = relationship("RouteStop", back_populates="order")
 
    def __repr__(self):
        return f"<Order id={self.id} status={self.status}>"
