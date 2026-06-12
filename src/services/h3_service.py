"""
src/services/h3_service.py

All H3 operations for the logistics platform.

H3 recap:
  - Resolution 9  (~174m hex) → stored on Location, Depot, RouteStop, VehiclePositionEvent
  - Resolution 8  (~460m hex) → stored on Zone, TrafficProfile

Every lat/lng that enters the system gets converted to an h3_index here
before being saved to the database.
"""

import h3
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCATION_RESOLUTION = 9    # fine-grained — individual addresses
ZONE_RESOLUTION     = 8    # coarse — neighbourhood / traffic zone


# ---------------------------------------------------------------------------
# Core conversions
# ---------------------------------------------------------------------------

def latlng_to_h3(lat: float, lng: float, resolution: int = LOCATION_RESOLUTION) -> str:
    """
    Convert a lat/lng coordinate to an H3 cell index.

    Usage:
        idx = latlng_to_h3(24.8608, 67.0104)
        # → "8928308xxxxxxxxx"  (resolution 9, ~174m hex)

        zone = latlng_to_h3(24.8608, 67.0104, resolution=ZONE_RESOLUTION)
        # → "8828308xxxxxxxxx"  (resolution 8, ~460m hex)
    """
    return h3.latlng_to_cell(lat, lng, resolution)


def h3_to_latlng(h3_index: str) -> Tuple[float, float]:
    """
    Get the center lat/lng of an H3 cell.
    Used when seeding the Zone table (we store center coords for easy mapping).

        lat, lng = h3_to_latlng("8928308xxxxxxxxx")
    """
    return h3.cell_to_latlng(h3_index)


def location_to_zone(h3_index_res9: str) -> str:
    """
    Given a resolution-9 location index, return its parent resolution-8 zone.

    This is the bridge between a delivery address and its traffic profile.

        zone_idx = location_to_zone(location.h3_index)
        # use zone_idx to query TrafficProfile
    """
    return h3.cell_to_parent(h3_index_res9, ZONE_RESOLUTION)


# ---------------------------------------------------------------------------
# Neighbour & clustering helpers
# ---------------------------------------------------------------------------

def get_neighbours(h3_index: str, ring_size: int = 1) -> List[str]:
    """
    Get all hexagons within `ring_size` rings of the given cell.
    ring_size=1 → the 6 direct neighbours + the cell itself (7 total)
    ring_size=2 → 19 cells, etc.

    Used for:
    - Clustering nearby orders before VRP
    - Expanding a traffic zone search when a zone has no profile
    """
    return list(h3.grid_disk(h3_index, ring_size))


def get_ring(h3_index: str, ring_size: int = 1) -> List[str]:
    """
    Get only the outer ring at exactly `ring_size` distance (excludes center).
    Useful for finding cells at a specific distance without inner ones.
    """
    return list(h3.grid_ring(h3_index, ring_size))


def h3_distance(h3_index_a: str, h3_index_b: str) -> int:
    """
    Grid distance between two H3 cells (number of hops, not km).
    Fast proximity check without computing actual road distance.

    e.g. distance of 0 = same cell, 1 = direct neighbour
    """
    return h3.grid_distance(h3_index_a, h3_index_b)


# ---------------------------------------------------------------------------
# Boundary helpers (for seeding & visualisation)
# ---------------------------------------------------------------------------

def h3_boundary_coords(h3_index: str) -> List[Tuple[float, float]]:
    """
    Returns the corner lat/lng coordinates of the hexagon boundary.
    Useful for rendering hex overlays on a map.

    Returns list of (lat, lng) tuples.
    """
    # h3.cell_to_boundary returns list of (lat, lng) tuples
    return list(h3.cell_to_boundary(h3_index))


def latlng_bbox_to_h3_cells(
    min_lat: float, min_lng: float,
    max_lat: float, max_lng: float,
    resolution: int = ZONE_RESOLUTION
) -> List[str]:
    """
    Fill a bounding box with H3 cells at the given resolution.
    Used in seed_zones.py to cover all of Karachi at once.

    Karachi rough bbox:
        min_lat=24.74, min_lng=66.85, max_lat=25.10, max_lng=67.35
    """
    # Build a GeoJSON polygon from the bbox corners
    bbox_polygon = {
        "type": "Polygon",
        "coordinates": [[
            [min_lng, min_lat],
            [max_lng, min_lat],
            [max_lng, max_lat],
            [min_lng, max_lat],
            [min_lng, min_lat],   # close the ring
        ]]
    }
    # h3.geo_to_cells fills the polygon with H3 cells
    return list(h3.geo_to_cells(bbox_polygon, resolution))


# ---------------------------------------------------------------------------
# Compact display helper
# ---------------------------------------------------------------------------

def h3_resolution(h3_index: str) -> int:
    """Return the resolution of any H3 index string."""
    return h3.get_resolution(h3_index)