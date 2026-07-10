# from sqlalchemy import (
#     Column, String, DateTime, Integer
# )
# from sqlalchemy.dialects.postgresql import UUID
# from sqlalchemy.orm import relationship
# from sqlalchemy.sql import func
# from db.models.base import Base, gen_uuid

# class Client(Base):
#     __tablename__ = "clients"
 
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     name = Column(String(255), nullable=False)
#     primary_contact_number = Column(String(20), nullable=True)
#     primary_contact_email = Column(String(255), nullable=True)
#     type = Column(String(50), nullable=False)
#     office_latitude = Column(String(50), nullable=True)
#     office_longitude = Column(String(50), nullable=True)

#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     created_by = Column(Integer, nullable=False)
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now())
#     updated_by = Column(Integer, nullable=False)