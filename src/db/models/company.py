from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, DateTime, Integer, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid
from src.core.enums import ServiceType

if TYPE_CHECKING:
    from src.db.models.user_company import UserCompany
    from src.db.models.depot import Depot
    from src.db.models.vehicle import Vehicle
    from src.db.models.driver import Driver
    from src.db.models.customer import Customer
    from src.db.models.order import Order
    from src.db.models.route_plan import RoutePlan
    from src.db.models.employee import Employee

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default="Asia/Karachi")
    # discriminator: whether this company runs nurses or technicians (never both)
    service_type: Mapped[Optional[ServiceType]] = mapped_column(Enum(ServiceType), nullable=True)
    head_office_location_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("locations.id"), nullable=True)
    is_deleted: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=False)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    user_companies: Mapped[list["UserCompany"]] = relationship("UserCompany", back_populates="company")
    depots: Mapped[list["Depot"]] = relationship("Depot", back_populates="company")
    vehicles: Mapped[list["Vehicle"]] = relationship("Vehicle", back_populates="company")
    drivers: Mapped[list["Driver"]] = relationship("Driver", back_populates="company")
    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="company")
    # cost_profiles: Mapped[list["CostProfile"]] = relationship("CostProfile", back_populates="company")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="company")
    route_plans: Mapped[list["RoutePlan"]] = relationship("RoutePlan", back_populates="company")
    employees: Mapped[list["Employee"]] = relationship("Employee", back_populates="company")

    def __repr__(self):
        return f"<Company id={self.id} name={self.name}>"
