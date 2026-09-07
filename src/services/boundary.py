"""
src/services/boundary.py

The service area, derived from ONE place name.

src/services/maps.py builds the routing graph with
``ox.graph_from_place(settings.MAP_PLACE)``. This module resolves the SAME name
to the same polygon via ``ox.geocode_to_gdf`` — the call graph_from_place makes
internally — and exposes it to the geocoder. That shared origin is the point:
change settings.MAP_PLACE and both the router and the search box move together,
so search can never offer a location the router cannot reach.

Two levels of filtering, because they cost very different amounts:

  bbox     — the rectangle around the polygon. Photon's only geographic filter,
             applied server-side by Photon itself, so junk never crosses the
             network. Loose: for Karachi Division the polygon is 0.52 deg^2 but
             its bbox is 1.62 deg^2, so ~2/3 of the rectangle is sea and desert.

  polygon  — the real shape. Exact, and cheap once loaded (a shapely `contains`
             on <=10 candidate points), so it runs on every response as the
             actual correctness guarantee.

The polygon comes from Nominatim, which rate-limits, so it is fetched once and
cached in Redis under a key derived from the place name — mirroring the
GRAPH_CACHE_KEY pattern in maps.py. A new MAP_PLACE yields a new key, so the
cache invalidates itself.
"""

from __future__ import annotations

import hashlib
import logging
import pickle
from typing import Optional

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from src.core.config import settings
from src.infrastructure.redis.redis import get_redis

logger = logging.getLogger(__name__)

# Bump the version suffix to force a refresh of every cached boundary.
_CACHE_VERSION = "v1"

_polygon: Optional[BaseGeometry] = None
_bbox: Optional[tuple[float, float, float, float]] = None


def _cache_key() -> str:
    """Redis key for the current MAP_PLACE. Hashed so any place name is safe."""
    digest = hashlib.sha1(settings.MAP_PLACE.encode("utf-8")).hexdigest()[:12]
    return f"boundary:{_CACHE_VERSION}:{digest}"


def _load_from_redis() -> Optional[BaseGeometry]:
    try:
        data = get_redis().get(_cache_key())
        return pickle.loads(data) if data is not None else None
    except Exception as e:
        logger.warning(f"Boundary: Redis load failed ({e}), falling through")
        return None


def _save_to_redis(poly: BaseGeometry) -> None:
    try:
        # No TTL: an administrative boundary is stable for years, and the key is
        # derived from the place name so a city change invalidates it anyway.
        get_redis().set(_cache_key(), pickle.dumps(poly, protocol=pickle.HIGHEST_PROTOCOL))
    except Exception as e:
        logger.warning(f"Boundary: Redis save failed ({e}), continuing without cache")


def _fetch_from_nominatim() -> BaseGeometry:
    """Resolve MAP_PLACE to a polygon. Slow (network) and rate-limited."""
    import osmnx as ox
    gdf = ox.geocode_to_gdf(settings.MAP_PLACE)
    return gdf.geometry.iloc[0]


def load_boundary(force_reload: bool = False) -> BaseGeometry:
    """
    The service-area polygon for settings.MAP_PLACE.

    Priority: in-memory singleton -> Redis -> Nominatim. Raises if all three
    fail; callers that must not break (the geocode endpoint) use
    ``get_bbox_or_none`` / ``is_inside`` instead, which degrade gracefully.
    """
    global _polygon, _bbox

    if _polygon is not None and not force_reload:
        return _polygon

    if not force_reload:
        cached = _load_from_redis()
        if cached is not None:
            logger.info("Boundary: loaded from Redis cache")
            _polygon, _bbox = cached, None
            return _polygon

    logger.info(f"Boundary: geocoding {settings.MAP_PLACE!r} via Nominatim...")
    _polygon = _fetch_from_nominatim()
    _bbox = None
    _save_to_redis(_polygon)
    return _polygon


def get_bbox() -> tuple[float, float, float, float]:
    """
    (west, south, east, north) around the service area — the order Photon's
    ``bbox`` parameter expects (minLon,minLat,maxLon,maxLat).
    """
    global _bbox
    if _bbox is None:
        west, south, east, north = load_boundary().bounds
        _bbox = (west, south, east, north)
    return _bbox


def get_bbox_or_none() -> Optional[tuple[float, float, float, float]]:
    """bbox if the boundary is available, else None. Never raises."""
    try:
        return get_bbox()
    except Exception as e:
        logger.warning(f"Boundary: bbox unavailable ({e}); geocode runs unfiltered")
        return None


def get_center() -> Optional[tuple[float, float]]:
    """
    (lat, lng) centroid of the service area, used as Photon's ``lat``/``lon``
    distance bias so central results outrank ones at the edge. Never raises.
    """
    try:
        c = load_boundary().centroid
        return (c.y, c.x)
    except Exception:
        return None


def is_inside(lat: float, lng: float) -> bool:
    """
    True if the point lies within the service-area polygon.

    Fails OPEN: if the boundary cannot be loaded, this returns True rather than
    rejecting every result. A geocoder that silently returns nothing is worse
    than one that occasionally offers a point just outside the line — and the
    bbox has usually already done the coarse filtering.
    """
    try:
        return load_boundary().contains(Point(lng, lat))
    except Exception:
        return True
