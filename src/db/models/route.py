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
from src.core.enums import RouteStatus

class Route(Base):
    __tablename__ = "routes"
 
    id                = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    plan_id           = Column(UUID(as_uuid=False), ForeignKey("route_plans.id"), nullable=False)
    vehicle_id        = Column(UUID(as_uuid=False), ForeignKey("vehicles.id"), nullable=False)
    driver_id         = Column(UUID(as_uuid=False), ForeignKey("drivers.id"))
    status            = Column(Enum(RouteStatus), default=RouteStatus.pending)
    total_distance_m  = Column(Integer)
    total_time_sec    = Column(Integer)
    total_weight_kg   = Column(Numeric(10, 3))
    estimated_cost    = Column(Numeric(12, 4))
    departure_time    = Column(DateTime(timezone=True))
    # full path as GeoJSON LineString for map rendering
    geometry          = Column(JSON)
 
    plan    = relationship("RoutePlan", back_populates="routes")
    vehicle = relationship("Vehicle",   back_populates="routes")
    driver  = relationship("Driver",    back_populates="routes")
    stops   = relationship("RouteStop", back_populates="route", order_by="RouteStop.stop_sequence")
    positions = relationship("VehiclePositionEvent", back_populates="route")
 
    def __repr__(self):
        return f"<Route id={self.id} vehicle={self.vehicle_id} status={self.status}>"
