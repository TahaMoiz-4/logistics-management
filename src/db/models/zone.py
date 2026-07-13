from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Float, Integer
from sqlalchemy.orm import relationship, mapped_column, Mapped
from src.db.models.base import Base, gen_uuid

if TYPE_CHECKING:
    from src.db.models.traffic_profile import TrafficProfile

class Zone(Base):
    """
    Master table of H3 hexagons we care about.
    The h3_index IS the primary key — no surrogate UUID needed.

    Resolution 8  (~460m hex)  is used here for zone-level profiles.
    Resolution 9  (~174m hex)  is stored on Location / Depot / RouteStop.
    You get from res-9 → res-8 in one h3.cell_to_parent(idx, 8) call.
    """
    __tablename__ = "zones"

    h3_index: Mapped[str] = mapped_column(String(20), primary_key=True)
    resolution: Mapped[int] = mapped_column(Integer, nullable=False)
    center_lat: Mapped[Optional[float]] = mapped_column(Float)
    center_lng: Mapped[Optional[float]] = mapped_column(Float)
    city: Mapped[Optional[str]] = mapped_column(String(128))
    # human-readable district name, e.g. "Clifton", "Saddar", "Korangi"
    label: Mapped[Optional[str]] = mapped_column(String(128))

    traffic_profiles: Mapped[list["TrafficProfile"]] = relationship("TrafficProfile", back_populates="zone")

    def __repr__(self):
        return f"<Zone h3={self.h3_index} label={self.label}>"
