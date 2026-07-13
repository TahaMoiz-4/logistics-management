# from sqlalchemy import (
#     Column, Integer, String, Numeric, ForeignKey
# )
# from sqlalchemy.dialects.postgresql import UUID
# from sqlalchemy.orm import relationship
# from sqlalchemy.sql import func
# from src.db.models.base import Base

# class CostProfile(Base):
#     __tablename__ = "cost_profiles"
 
#     id               = Column(Integer, primary_key=True, autoincrement=True)
#     company_id       = Column(Integer, ForeignKey("companies.id"), nullable=True)
#     fuel_cost_per_km = Column(Numeric(10, 4), nullable=False)   
#     driver_hourly    = Column(Numeric(10, 4), nullable=False)   
#     cost_per_kg      = Column(Numeric(10, 4))
#     monthly_fixed_cost  = Column(Numeric(10, 4))                   
#     currency         = Column(String(8), default="PKR")
 
#     company  = relationship("Company",  back_populates="cost_profiles")
#     vehicles = relationship("Vehicle",  back_populates="cost_profile")
 
#     def __repr__(self):
#         return f"<CostProfile id={self.id} company_id={self.company_id} company_name={self.company.name}>"