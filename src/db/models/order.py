from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, Numeric, Text, DateTime, Date, ForeignKey, Enum, Integer
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
from src.db.models.base import Base, gen_uuid
from src.core.enums import OrderPriority, OrderStatus, NurseClinicalSkill, TechnicianSkills

if TYPE_CHECKING:
    from src.db.models.company import Company
    from src.db.models.customer import Customer
    from src.db.models.location import Location
    from src.db.models.worker_assignment_stop import WorkerAssignmentStop

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    # null pickup = starts from depot
    location_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("locations.id"), nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), nullable=True)
    volume_m3: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    # Only one of these is populated, determined by the company's service_type.
    # Nurse-companies use required_nurse_skills; technician-companies use required_tech_skills.
    required_nurse_skills: Mapped[Optional[list[NurseClinicalSkill]]] = mapped_column(ARRAY(Enum(NurseClinicalSkill)), nullable=True)
    required_tech_skills: Mapped[Optional[list[TechnicianSkills]]] = mapped_column(ARRAY(Enum(TechnicianSkills)), nullable=True)
    # the calendar day this order is to be serviced. Authoritative for
    # scheduling: a route plan solves exactly one service_date's orders (the
    # solver is single-day by construction). timewindow_start/end refine the
    # within-day window; service_date decides which day.
    service_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    timewindow_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    timewindow_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # how long the worker spends performing this order, in minutes.
    # Loader falls back to a config default when null.
    service_duration_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    priority: Mapped[Optional[OrderPriority]] = mapped_column(Enum(OrderPriority), default=OrderPriority.normal)
    status: Mapped[Optional[OrderStatus]] = mapped_column(Enum(OrderStatus), default=OrderStatus.pending)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="orders")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    location: Mapped[Optional["Location"]] = relationship("Location", back_populates="orders")
    # delivery_window: Mapped[Optional["DeliveryWindow"]] = relationship("DeliveryWindow", back_populates="order", uselist=False)
    worker_assignment_stops: Mapped[list["WorkerAssignmentStop"]] = relationship("WorkerAssignmentStop", back_populates="order")

    def __repr__(self):
        return f"<Order id={self.id} status={self.status}>"
