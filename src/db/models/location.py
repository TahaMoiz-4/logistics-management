from sqlalchemy import (
    Column, String, Float, 
    Text, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid

class Location(Base):
    __tablename__ = "locations"
 
    id          = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    # nullable: depot-linked locations won't have a customer
    customer_id = Column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=True)
    label       = Column(String(128))          # e.g. "Home", "Office"
    lat         = Column(Float, nullable=False)
    lng         = Column(Float, nullable=False)
    # H3 index at resolution 9 — the primary spatial key used everywhere
    h3_index    = Column(String(20), nullable=False, index=True)
    address_text= Column(Text)
    city        = Column(String(128))
 
    customer        = relationship("Customer",  back_populates="locations")
    pickup_orders   = relationship("Order", foreign_keys="Order.pickup_location_id",  back_populates="pickup_location")
    dropoff_orders  = relationship("Order", foreign_keys="Order.dropoff_location_id", back_populates="dropoff_location")
    route_stops     = relationship("RouteStop", back_populates="location")
 
    def __repr__(self):
        return f"<Location id={self.id} h3={self.h3_index}>"
