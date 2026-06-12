from sqlalchemy import (
    Column, String, Numeric, Boolean, Time, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid

class Driver(Base):
    __tablename__ = "drivers"
 
    id               = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id       = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)
    # nullable: a driver may be unassigned to a vehicle between routes
    vehicle_id       = Column(UUID(as_uuid=False), ForeignKey("vehicles.id"), nullable=True)
    name             = Column(String(255), nullable=False)
    phone            = Column(String(32))
    license_number   = Column(String(64))
    shift_start      = Column(Time)           # e.g. 08:00
    shift_end        = Column(Time)           # e.g. 18:00
    max_hours_per_day= Column(Numeric(4, 2), default=10)
    is_active        = Column(Boolean, default=True)
 
    company = relationship("Company", back_populates="drivers")
    vehicle = relationship("Vehicle", back_populates="driver")
    routes  = relationship("Route",   back_populates="driver")
 
    def __repr__(self):
        return f"<Driver id={self.id} name={self.name}>"
