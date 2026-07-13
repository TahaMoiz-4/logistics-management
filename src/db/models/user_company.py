from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from src.db.models.base import Base

if TYPE_CHECKING:
    from src.db.models.sys_users import SysUsers
    from src.db.models.company import Company

class UserCompany(Base):
    __tablename__ = "users_companies"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_users.id"), primary_key=True, nullable=False)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), primary_key=True, nullable=False)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    user: Mapped["SysUsers"] = relationship("SysUsers", back_populates="user_companies")
    company: Mapped["Company"] = relationship("Company", back_populates="user_companies")

    def __repr__(self):
        return f"<UserCompany id={self.id} user_id={self.user_id} company_id={self.company_id}>"
