"""src/schemas/geocode.py — address search results (see src/services/photon.py)."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class GeocodeResult(BaseModel):
    """
    One suggestion in the address dropdown.

    ``label`` is the bold first line, ``context`` the muted second. ``lat``/
    ``lng`` are what the caller ultimately POSTs to /v1/orders, and
    ``address_text`` is the flattened form persisted to Location.address_text —
    so orders read as addresses instead of bare decimals.
    """
    label: str
    context: str = ""
    address_text: str
    lat: float
    lng: float
    type: Optional[str] = None          # house | street | locality | district | city
    osm_id: Optional[int] = None
    osm_type: Optional[str] = None      # N | W | R
    postcode: Optional[str] = None

    # Null when the road graph is not loaded, so the console can tell "we did not
    # check" apart from "we checked and it is fine".
    routable: Optional[bool] = None
    snap_distance_m: Optional[float] = None


class GeocodeSearchOut(BaseModel):
    query: str
    results: list[GeocodeResult]
