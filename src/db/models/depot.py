from sqlalchemy import (
    Column, String, Float, Boolean,
    Text, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid

class Depot(Base):
    __tablename__ = "depots"
 
    id         = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)
    name       = Column(String(255), nullable=False)
    lat        = Column(Float, nullable=False)
    lng        = Column(Float, nullable=False)
    # H3 index at resolution 9 — pre-computed when the depot is created
    h3_index   = Column(String(20), nullable=False, index=True)
    address    = Column(Text)
    is_active  = Column(Boolean, default=True)
 
    company  = relationship("Company",  back_populates="depots")
    vehicles = relationship("Vehicle",  back_populates="depot")
    plans    = relationship("RoutePlan", back_populates="depot")
 
    def __repr__(self):
        return f"<Depot id={self.id} name={self.name}>"
