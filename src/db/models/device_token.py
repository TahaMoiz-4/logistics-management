from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Integer, String, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from src.db.models.base import Base
from src.core.enums import DevicePlatform

if TYPE_CHECKING:
    from src.db.models.employee import Employee

class DeviceToken(Base):
    """
    An FCM push target for a field worker's device. A worker (Employee) may have
    several devices; the mobile app registers/refreshes its token on every login
    (tokens rotate). The backend sends job-alert pushes to a worker's active
    tokens on plan approval.
    """
    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(512), nullable=False)
    platform: Mapped[Optional[DevicePlatform]] = mapped_column(Enum(DevicePlatform), default=DevicePlatform.android)
    active: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="device_tokens")

    def __repr__(self):
        return f"<DeviceToken id={self.id} employee={self.employee_id} platform={self.platform}>"
