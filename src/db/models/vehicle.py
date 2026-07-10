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
from src.core.enums import VehicleType, FuelType

class Vehicle(Base):
    __tablename__ = "vehicles"
 
    id              = Column(Integer, primary_key=True, autoincrement=True)
    company_id      = Column(Integer, ForeignKey("companies.id"), nullable=False)
    depot_id        = Column(Integer, ForeignKey("depots.id"), nullable=False)
    permanent_depot_id = Column(Integer, ForeignKey("depots.id"), nullable=True)
    cost_profile_id = Column(Integer, ForeignKey("cost_profiles.id"))
    license_plate   = Column(String(32), nullable=False)
    type            = Column(Enum(VehicleType), nullable=False)
    max_weight_kg   = Column(Numeric(10, 2), nullable=False)
    max_volume_m3   = Column(Numeric(10, 3))
    avg_speed_kmh   = Column(Numeric(6, 2), default=40)
    fuel_type       = Column(Enum(FuelType), default=FuelType.petrol)
    is_active       = Column(Boolean, default=True)
 
    company      = relationship("Company",     back_populates="vehicles")
    depot        = relationship("Depot",       back_populates="vehicles")
    cost_profile = relationship("CostProfile", back_populates="vehicles")
    driver       = relationship("Driver",      back_populates="vehicle", uselist=False)
    routes       = relationship("Route",       back_populates="vehicle")
    positions    = relationship("VehiclePositionEvent", back_populates="vehicle")
 
    def __repr__(self):
        return f"<Vehicle id={self.id} plate={self.license_plate}>"
