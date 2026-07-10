from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.models.base import Base

class UserCompany(Base):
    __tablename__ = "users_companies"
 
    user_id       = Column(Integer, ForeignKey("sys_users.id"), nullable=False)
    company_id    = Column(Integer, ForeignKey("companies.id"), nullable=False)

    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    created_by    = Column(Integer, nullable=False)
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by    = Column(Integer, nullable=False)

    user          = relationship("SysUsers", back_populates="user_companies")
    company       = relationship("Company", back_populates="user_companies")

    def __repr__(self):
        return f"<UserCompany id={self.id} user_id={self.user_id} company_id={self.company_id}>"
    