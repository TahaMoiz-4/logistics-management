from sqlalchemy import (
    Boolean, Column, Integer, String, DateTime, Float
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid

class Company(Base):
    __tablename__ = "companies"
 
    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(255), nullable=False)
    contact_number = Column(String(20), nullable=True)
    contact_email = Column(String(255), nullable=True)
    timezone      = Column(String(64), default="Asia/Karachi")
    office_latitude = Column(Float, nullable=True)
    office_longitude = Column(Float, nullable=True)
    is_deleted     = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(Integer, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, nullable=True)

    user_companies = relationship("UserCompany", back_populates="company")
    depots        = relationship("Depot",        back_populates="company")
    vehicles      = relationship("Vehicle",      back_populates="company")
    drivers       = relationship("Driver",       back_populates="company")
    customers     = relationship("Customer",     back_populates="company")
    cost_profiles = relationship("CostProfile",  back_populates="company")
    orders        = relationship("Order",        back_populates="company")
    route_plans   = relationship("RoutePlan",    back_populates="company")
    employees = relationship("Employee", back_populates="company")
    
    def __repr__(self):
        return f"<Company id={self.id} name={self.name}>"
