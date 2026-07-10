from sqlalchemy import (
    Column, Integer, String, DateTime, true
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid

class SysUsers(Base):
    __tablename__ = "sys_users"
 
    id            = Column(Integer, primary_key=True, autoincrement=True)
    username      = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role          = Column(String(64), nullable=False)  # e.g. 'admin', 'user'
    primary_contact_number = Column(String(20), nullable=True)
    primary_contact_email  = Column(String(255), nullable=True)
        
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    created_by    = Column(Integer, nullable=True)
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by    = Column(Integer, nullable=True)

    user_companies = relationship("UserCompany", back_populates="user")

    def __repr__(self):
        return f"<SysUser id={self.id} username={self.username} role={self.role} company_id={self.company_id}>"