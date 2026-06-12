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
from src.core.enums import DayType, TrafficSource

class TrafficProfile(Base):
    """
    For a given Zone + day_type + hour band → travel time multiplier.
 
    multiplier = 1.0  means no congestion (free flow)
    multiplier = 1.8  means travel takes 80% longer than the OSMnx base time
    multiplier = 2.5  means 2.5× the free-flow time (heavy jam)
 
    Synthetic seed values are hand-coded per Karachi's known patterns.
    The `source` field will flip to 'learned' once we derive from real data.
    """
    __tablename__ = "traffic_profiles"
 
    id         = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    h3_index   = Column(String(20), ForeignKey("zones.h3_index"), nullable=False)
    day_type   = Column(Enum(DayType), nullable=False)
    hour_start = Column(Integer, nullable=False)   # 0–23  inclusive
    hour_end   = Column(Integer, nullable=False)   # 0–23  inclusive
    multiplier = Column(Numeric(5, 3), nullable=False)
    # nullable — set only when we want road-class-level granularity
    road_type  = Column(String(64))
    source     = Column(Enum(TrafficSource), default=TrafficSource.synthetic)
 
    zone = relationship("Zone", back_populates="traffic_profiles")
 
    __table_args__ = (
        # fast lookup: given a hex + day + hour, find the multiplier instantly
        Index("ix_traffic_profile_lookup", "h3_index", "day_type", "hour_start", "hour_end"),
    )
 
    def __repr__(self):
        return f"<TrafficProfile h3={self.h3_index} {self.day_type} {self.hour_start}–{self.hour_end} ×{self.multiplier}>"
