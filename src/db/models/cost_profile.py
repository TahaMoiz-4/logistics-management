from sqlalchemy import (
    Column, String, Numeric, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid

class CostProfile(Base):
    __tablename__ = "cost_profiles"
 
    id               = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id       = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)
    name             = Column(String(255), nullable=False)
    fuel_cost_per_km = Column(Numeric(10, 4), nullable=False)   # PKR per km
    driver_hourly    = Column(Numeric(10, 4), nullable=False)   # PKR per hour
    cost_per_kg      = Column(Numeric(10, 4))                   # nullable
    currency         = Column(String(8), default="PKR")
 
    company  = relationship("Company",  back_populates="cost_profiles")
    vehicles = relationship("Vehicle",  back_populates="cost_profile")
 
    def __repr__(self):
        return f"<CostProfile id={self.id} name={self.name}>"
