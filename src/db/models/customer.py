from sqlalchemy import (
    Column, String, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid

class Customer(Base):
    __tablename__ = "customers"
 
    id         = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)
    name       = Column(String(255), nullable=False)
    email      = Column(String(255))
    phone      = Column(String(32))
 
    company   = relationship("Company",  back_populates="customers")
    locations = relationship("Location", back_populates="customer")
    orders    = relationship("Order",    back_populates="customer")
 
    def __repr__(self):
        return f"<Customer id={self.id} name={self.name}>"
