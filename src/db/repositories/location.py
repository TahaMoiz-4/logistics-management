"""
src/db/repositories/location.py

Shared helper for creating/updating Location rows. Customer/Depot/Order writes
need a Location with a computed H3 index; this centralizes that so lat/lng always
get an h3_index without each router repeating the h3 call.
"""

from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import Location
from src.core.enums import LocationTypes


class LocationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, location_id: int) -> Optional[Location]:
        return (
            self.db.query(Location)
            .filter(Location.id == location_id, Location.deleted_at.is_(None))
            .first()
        )

    def create(self, lat: float, lng: float, actor_id: int,
               type_: Optional[LocationTypes] = None,
               address_text: Optional[str] = None) -> Location:
        from src.services.h3_service import latlng_to_h3
        loc = Location(
            lat=lat, lng=lng, h3_index=latlng_to_h3(lat, lng),
            type=type_, address_text=address_text, created_by=actor_id,
        )
        self.db.add(loc)
        self.db.flush()          # caller commits within its own transaction
        return loc

    def update_coords(self, loc: Location, lat: float, lng: float, actor_id: int,
                      address_text: Optional[str] = None) -> Location:
        from src.services.h3_service import latlng_to_h3
        loc.lat, loc.lng = lat, lng
        loc.h3_index = latlng_to_h3(lat, lng)
        if address_text is not None:
            loc.address_text = address_text
        loc.updated_by = actor_id
        self.db.flush()
        return loc
