from sqlalchemy import (
    Column, String, DateTime
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid

class Company(Base):
    __tablename__ = "companies"
 
    id            = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name          = Column(String(255), nullable=False)
    contact_email = Column(String(255))
    timezone      = Column(String(64), default="Asia/Karachi")
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
 
    # relationships
    depots        = relationship("Depot",        back_populates="company")
    vehicles      = relationship("Vehicle",      back_populates="company")
    drivers       = relationship("Driver",       back_populates="company")
    customers     = relationship("Customer",     back_populates="company")
    cost_profiles = relationship("CostProfile",  back_populates="company")
    orders        = relationship("Order",        back_populates="company")
    route_plans   = relationship("RoutePlan",    back_populates="company")
 
    depots        = relationship("Depot",        back_populates="company")
    vehicles      = relationship("Vehicle",      back_populates="company")
    drivers       = relationship("Driver",       back_populates="company")
    customers     = relationship("Customer",     back_populates="company")
    cost_profiles = relationship("CostProfile",  back_populates="company")
    orders        = relationship("Order",        back_populates="company")
    route_plans   = relationship("RoutePlan",    back_populates="company")

    def __repr__(self):
        return f"<Company id={self.id} name={self.name}>"
