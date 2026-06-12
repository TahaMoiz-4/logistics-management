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
from src.core.enums import PositionSource

class VehiclePositionEvent(Base):
    """
    Append-only log of vehicle positions.
 
    In pre-trip mode this table is empty.
    When live tracking is active (real GPS or simulator), rows are
    inserted via POST /vehicles/{id}/position and trigger re-routing logic.
    """
    __tablename__ = "vehicle_position_events"
 
    id          = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    vehicle_id  = Column(UUID(as_uuid=False), ForeignKey("vehicles.id"), nullable=False)
    route_id    = Column(UUID(as_uuid=False), ForeignKey("routes.id"), nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    lat         = Column(Float, nullable=False)
    lng         = Column(Float, nullable=False)
    h3_index    = Column(String(20), nullable=False, index=True)
    speed_kmh   = Column(Numeric(6, 2))
    source      = Column(Enum(PositionSource), default=PositionSource.gps)
 
    vehicle = relationship("Vehicle", back_populates="positions")
    route   = relationship("Route",   back_populates="positions")
 
    __table_args__ = (
        Index("ix_position_vehicle_time", "vehicle_id", "recorded_at"),
    )
 
    def __repr__(self):
        return f"<VehiclePositionEvent vehicle={self.vehicle_id} at={self.recorded_at}>"
