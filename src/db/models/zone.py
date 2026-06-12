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

class Zone(Base):
    """
    Master table of H3 hexagons we care about.
    The h3_index IS the primary key — no surrogate UUID needed.
 
    Resolution 8  (~460m hex)  is used here for zone-level profiles.
    Resolution 9  (~174m hex)  is stored on Location / Depot / RouteStop.
    You get from res-9 → res-8 in one h3.cell_to_parent(idx, 8) call.
    """
    __tablename__ = "zones"
 
    h3_index   = Column(String(20), primary_key=True)
    resolution = Column(Integer, nullable=False)
    center_lat = Column(Float)
    center_lng = Column(Float)
    city       = Column(String(128))
    # human-readable district name, e.g. "Clifton", "Saddar", "Korangi"
    label      = Column(String(128))
 
    traffic_profiles = relationship("TrafficProfile", back_populates="zone")
 
    def __repr__(self):
        return f"<Zone h3={self.h3_index} label={self.label}>"
