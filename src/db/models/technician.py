from sqlalchemy import (
    Column, String, DateTime, Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.models.base import Base, gen_uuid

class Technician(Base):
    __tablename__ = "technicians"
 
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    contact_number = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Technician id={self.id} name={self.name}>"