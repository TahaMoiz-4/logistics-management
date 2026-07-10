from sqlalchemy import (
    Column, String, DateTime, Integer, Time, ForeignKey, Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.models.base import Base, gen_uuid

class Employee(Base):
    __tablename__ = "employees"
 
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    contact_number = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    shift_start = Column(Time, nullable=True)
    shift_end = Column(Time, nullable=True)
    is_active = Column(Boolean, default=True)
    
    company_id =  Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)

    company = relationship("Company", back_populates="emoloyees")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(UUID(as_uuid=False), nullable=True)

    def __repr__(self):
        return f"<Employee id={self.id} name={self.name}>"
    