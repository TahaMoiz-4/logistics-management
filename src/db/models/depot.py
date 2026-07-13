from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, String, ForeignKey, Integer, Enum
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid
from src.core.enums import OperationalStatus

if TYPE_CHECKING:
    from src.db.models.company import Company
    from src.db.models.vehicle import Vehicle
    from src.db.models.route_plan import RoutePlan

class Depot(Base):
    __tablename__ = "depots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("locations.id"), nullable=True)
    operational_status: Mapped[Optional[OperationalStatus]] = mapped_column(Enum(OperationalStatus), default=OperationalStatus.active)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="depots")
    vehicles: Mapped[list["Vehicle"]] = relationship("Vehicle", back_populates="depot")
    plans: Mapped[list["RoutePlan"]] = relationship("RoutePlan", back_populates="depot")

    def __repr__(self):
        return f"<Depot id={self.id} name={self.name}>"
