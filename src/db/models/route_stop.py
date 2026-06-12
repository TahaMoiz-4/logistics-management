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
from src.core.enums import StopType

class RouteStop(Base):
    __tablename__ = "route_stops"
 
    id                   = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    route_id             = Column(UUID(as_uuid=False), ForeignKey("routes.id"), nullable=False)
    # null for depot_start / depot_end stops
    order_id             = Column(UUID(as_uuid=False), ForeignKey("orders.id"), nullable=True)
    location_id          = Column(UUID(as_uuid=False), ForeignKey("locations.id"), nullable=False)
    stop_sequence        = Column(Integer, nullable=False)
    stop_type            = Column(Enum(StopType), nullable=False)
    eta                  = Column(DateTime(timezone=True))
    eta_window_start     = Column(DateTime(timezone=True))
    eta_window_end       = Column(DateTime(timezone=True))
    distance_from_prev_m = Column(Integer)
    time_from_prev_sec   = Column(Integer)
    # filled in real-time when live tracking is active
    arrived_at           = Column(DateTime(timezone=True))
    departed_at          = Column(DateTime(timezone=True))
 
    route    = relationship("Route",    back_populates="stops")
    order    = relationship("Order",    back_populates="route_stops")
    location = relationship("Location", back_populates="route_stops")
 
    def __repr__(self):
        return f"<RouteStop route={self.route_id} seq={self.stop_sequence} type={self.stop_type}>"
