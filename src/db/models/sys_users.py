from sqlalchemy import (
    Column, String, DateTime
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid

class SysUsers(Base):
    __tablename__ = "sys_users"
 
    id            = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    username      = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role          = Column(String(64), nullable=False)  # e.g. 'admin', 'user'
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<SysUser id={self.id} username={self.username} role={self.role}>"