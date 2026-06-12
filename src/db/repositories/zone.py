"""
src/db/repositories/zone_repository.py

Database queries for Zone and TrafficProfile models.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.db.models import Zone, TrafficProfile
from src.core.enums import DayType


class ZoneRepository:

    def __init__(self, db: Session):
        self.db = db

    # ── Zone ────────────────────────────────────────────────────────────────

    def get_zone(self, h3_index: str) -> Optional[Zone]:
        return self.db.query(Zone).filter(Zone.h3_index == h3_index).first()

    def bulk_upsert_zones(self, zones: List[dict]) -> int:
        """
        Insert zones, skip if h3_index already exists.
        zones: list of dicts with keys: h3_index, resolution, center_lat,
               center_lng, city, label
        Returns count of newly inserted rows.
        """
        inserted = 0
        existing = {
            z.h3_index
            for z in self.db.query(Zone.h3_index).all()
        }
        for z in zones:
            if z["h3_index"] not in existing:
                self.db.add(Zone(**z))
                inserted += 1
        self.db.commit()
        return inserted

    def get_all_zones(self, city: str = "Karachi") -> List[Zone]:
        return self.db.query(Zone).filter(Zone.city == city).all()

    # ── TrafficProfile ───────────────────────────────────────────────────────

    def get_multiplier(
        self,
        h3_index: str,
        day_type: DayType,
        hour: int,
    ) -> float:
        """
        Fetch the traffic multiplier for a zone at a given day_type + hour.
        Returns 1.0 (free flow) if no profile found.
        """
        profile = (
            self.db.query(TrafficProfile)
            .filter(
                TrafficProfile.h3_index   == h3_index,
                TrafficProfile.day_type   == day_type,
                TrafficProfile.hour_start <= hour,
                TrafficProfile.hour_end   >  hour,
            )
            .first()
        )
        return float(profile.multiplier) if profile else 1.0

    def bulk_insert_profiles(self, profiles: List[dict]) -> int:
        """
        Insert traffic profiles. Skips duplicates by checking
        (h3_index, day_type, hour_start, hour_end) uniqueness.
        """
        inserted = 0
        for p in profiles:
            exists = (
                self.db.query(TrafficProfile)
                .filter(
                    TrafficProfile.h3_index   == p["h3_index"],
                    TrafficProfile.day_type   == p["day_type"],
                    TrafficProfile.hour_start == p["hour_start"],
                    TrafficProfile.hour_end   == p["hour_end"],
                )
                .first()
            )
            if not exists:
                self.db.add(TrafficProfile(**p))
                inserted += 1
        self.db.commit()
        return inserted

    def get_profiles_for_zone(self, h3_index: str) -> List[TrafficProfile]:
        return (
            self.db.query(TrafficProfile)
            .filter(TrafficProfile.h3_index == h3_index)
            .order_by(TrafficProfile.day_type, TrafficProfile.hour_start)
            .all()
        )