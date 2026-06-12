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
from src.core.enums import PlanStatus

class RoutePlan(Base):
    __tablename__ = "route_plans"
 
    id                  = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id          = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)
    depot_id            = Column(UUID(as_uuid=False), ForeignKey("depots.id"), nullable=False)
    name                = Column(String(255))
    planned_date        = Column(Date, nullable=False)
    status              = Column(Enum(PlanStatus), default=PlanStatus.draft)
    # snapshot of solver config at time of optimization, e.g. {"max_vehicles": 5}
    optimization_params = Column(JSON, default=dict)
    total_orders        = Column(Integer, default=0)
    total_routes        = Column(Integer, default=0)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    optimized_at        = Column(DateTime(timezone=True))
 
    company = relationship("Company",  back_populates="route_plans")
    depot   = relationship("Depot",    back_populates="plans")
    routes  = relationship("Route",    back_populates="plan")
 
    def __repr__(self):
        return f"<RoutePlan id={self.id} date={self.planned_date} status={self.status}>"
