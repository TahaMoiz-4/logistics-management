from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, Float, Text, Integer, Enum, DateTime
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from src.db.models.base import Base, gen_uuid
from src.core.enums import LocationTypes

if TYPE_CHECKING:
    from src.db.models.order import Order
    from src.db.models.driver_route_stop import DriverRouteStop
    from src.db.models.customer import Customer

class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # nullable: depot-linked locations won't have a customer
    type: Mapped[Optional[LocationTypes]] = mapped_column(Enum(LocationTypes), nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    # H3 index at resolution 9 — the primary spatial key used everywhere
    h3_index: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    address_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    customer : Mapped["Customer"] = relationship("Customer",  back_populates="location")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="location")
    driver_route_stops: Mapped[list["DriverRouteStop"]] = relationship("DriverRouteStop", back_populates="location")

    def __repr__(self):
        return f"<Location id={self.id} h3={self.h3_index}>"
