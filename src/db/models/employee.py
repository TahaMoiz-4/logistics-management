from datetime import datetime, time
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, DateTime, Integer, Time, ForeignKey, Enum
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid
from src.core.enums import OperationalStatus

if TYPE_CHECKING:
    from src.db.models.company import Company
    from src.db.models.technician import Technician
    from src.db.models.nurse import Nurse
    from src.db.models.driver import Driver
    from src.db.models.device_token import DeviceToken

class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cnic: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    shift_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    shift_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    operational_status: Mapped[Optional[OperationalStatus]] = mapped_column(Enum(OperationalStatus), default=OperationalStatus.active)
    # ── mobile login (field workers authenticate as an Employee) ──────────────
    username: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # ── availability (worker marks self unavailable; admin sees who + why) ────
    unavailable_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="employees")
    technicians: Mapped[list["Technician"]] = relationship("Technician", back_populates="employee")
    nurses: Mapped[list["Nurse"]] = relationship("Nurse", back_populates="employee")
    drivers: Mapped[list["Driver"]] = relationship("Driver", back_populates="employee")
    device_tokens: Mapped[list["DeviceToken"]] = relationship("DeviceToken", back_populates="employee")

    def __repr__(self):
        return f"<Employee ID={self.id} Name={self.name}> Company ID={self.company_id}"
