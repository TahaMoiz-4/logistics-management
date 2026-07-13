from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Float, Numeric, DateTime, Integer, Enum, Index
)
from sqlalchemy.orm import mapped_column, Mapped
from src.db.models.base import Base
from src.core.enums import PositionSource, ServiceType

class WorkerPositionEvent(Base):
    """
    Append-only GPS log for any field worker (nurse / technician / driver).

    VehiclePositionEvent is vehicle-keyed and only covers drivers with a vehicle;
    nurses/techs share location during a shift too, so their pings land here.
    ``worker_id`` + ``worker_type`` identify the domain row (nurses/technicians/
    drivers). A driver's app may write to both this and VehiclePositionEvent.
    """
    __tablename__ = "worker_position_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_type: Mapped[ServiceType] = mapped_column(Enum(ServiceType), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    h3_index: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    accuracy_m: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    source: Mapped[Optional[PositionSource]] = mapped_column(Enum(PositionSource), default=PositionSource.gps)

    __table_args__ = (
        Index("ix_worker_position_worker_time", "worker_type", "worker_id", "recorded_at"),
    )

    def __repr__(self):
        return f"<WorkerPositionEvent {self.worker_type}:{self.worker_id} at={self.recorded_at}>"
