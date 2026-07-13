from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    DateTime, Integer, Float, ForeignKey, Enum
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid
from src.core.enums import TechnicianSkills, OperationalStatus

if TYPE_CHECKING:
    from src.db.models.employee import Employee

class Technician(Base):
    __tablename__ = "technicians"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("employees.id"), nullable=True)
    orders_completed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.0)
    skills: Mapped[list[TechnicianSkills]] = mapped_column(ARRAY(Enum(TechnicianSkills)), nullable=True)
    operational_status: Mapped[Optional[OperationalStatus]] = mapped_column(Enum(OperationalStatus), default=OperationalStatus.active)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="technicians")

    def __repr__(self):
        return f"<Technician id={self.id}>"
