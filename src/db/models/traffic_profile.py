from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, Integer, Numeric, ForeignKey, Enum, Index
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from src.db.models.base import Base, gen_uuid
from src.core.enums import DayType, TrafficSource

if TYPE_CHECKING:
    from src.db.models.zone import Zone

class TrafficProfile(Base):
    __tablename__ = "traffic_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    h3_index: Mapped[str] = mapped_column(String(20), ForeignKey("zones.h3_index"), nullable=False)
    day_type: Mapped[DayType] = mapped_column(Enum(DayType), nullable=False)
    hour_start: Mapped[int] = mapped_column(Integer, nullable=False)   # 0–23  inclusive
    hour_end: Mapped[int] = mapped_column(Integer, nullable=False)   # 0–23  inclusive
    multiplier: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    road_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source: Mapped[Optional[TrafficSource]] = mapped_column(Enum(TrafficSource), default=TrafficSource.synthetic)

    zone: Mapped["Zone"] = relationship("Zone", back_populates="traffic_profiles")

    __table_args__ = (
        # fast lookup: given a hex + day + hour, find the multiplier instantly
        Index("ix_traffic_profile_lookup", "h3_index", "day_type", "hour_start", "hour_end"),
    )

    def __repr__(self):
        return f"<TrafficProfile h3={self.h3_index} {self.day_type} {self.hour_start}–{self.hour_end} ×{self.multiplier}>"
