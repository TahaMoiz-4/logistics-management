from sqlalchemy import (
    Column, String, Numeric, Boolean, Time, ForeignKey, Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid

class Driver(Base):
    __tablename__ = "drivers"
 
    id               = Column(Integer, primary_key=True, default=gen_uuid)
    company_id       = Column(Integer, ForeignKey("companies.id"), nullable=False)
    vehicle_id       = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    name             = Column(String(255), nullable=False)
    phone            = Column(String(32))
    license_number   = Column(String(64))
    shift_start      = Column(Time)
    shift_end        = Column(Time)        
    max_hours_per_day= Column(Numeric(4, 2), default=10)
    is_active        = Column(Boolean, default=True)
 
    company = relationship("Company", back_populates="drivers")
    vehicle = relationship("Vehicle", back_populates="driver")
    routes  = relationship("Route",   back_populates="driver")
 
    def __repr__(self):
        return f"<Driver id={self.id} name={self.name}>"
