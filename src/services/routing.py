import logging
from datetime import datetime

import networkx as nx
from sqlalchemy.orm import Session

from src.services.maps import (
    apply_traffic_to_graph,
    get_nearest_node,
    route_to_geojson,
)
from src.services.h3_service import latlng_to_h3, location_to_zone
from src.core.enums import DayType
from src.exceptions.routing import NoRouteFound
from src.schemas.routing import RouteResult

import osmnx as ox

logger = logging.getLogger(__name__)
# ---------------------------------------------------------------------------
# Day type helper
# ---------------------------------------------------------------------------

def _get_day_type(dt: datetime) -> DayType:
    weekday = dt.weekday()   # 0=Mon … 6=Sun
    if weekday == 4:
        return DayType.friday
    elif weekday == 5:
        return DayType.saturday
    elif weekday == 6:
        return DayType.sunday
    return DayType.weekday


# ---------------------------------------------------------------------------
# Multiplier lookup
# ---------------------------------------------------------------------------

def get_multiplier_for_location(
    lat: float,
    lng: float,
    dt: datetime,
    db: Session,
) -> float:
    """
    Convert lat/lng → H3 res-9 → res-8 zone → query TrafficProfile.
    Returns 1.0 if no profile found (free-flow fallback).
    """
    from src.db.models import TrafficProfile

    h3_res9  = latlng_to_h3(lat, lng)           # resolution 9
    zone_idx = location_to_zone(h3_res9)         # resolution 8
    hour     = dt.hour
    day_type = _get_day_type(dt)

    profile = (
        db.query(TrafficProfile)
        .filter(
            TrafficProfile.h3_index   == zone_idx,
            TrafficProfile.day_type   == day_type,
            TrafficProfile.hour_start <= hour,
            TrafficProfile.hour_end   >  hour,
        )
        .first()
    )

    if profile is None:
        logger.debug(
            f"No traffic profile for zone={zone_idx} "
            f"day={day_type} hour={hour} — using 1.0"
        )
        return 1.0

    return float(profile.multiplier)


# ---------------------------------------------------------------------------
# Core routing function
# ---------------------------------------------------------------------------

def route_between(
    G:            nx.MultiDiGraph,
    origin_lat:   float,
    origin_lng:   float,
    dest_lat:     float,
    dest_lng:     float,
    departure_dt: datetime,
    db:           Session,
) -> RouteResult:
    """
    Find the fastest route between two points, adjusted for traffic.

    Args:
        G:            Road network graph (loaded via maps.load_graph())
        origin_lat:   Origin latitude
        origin_lng:   Origin longitude
        dest_lat:     Destination latitude
        dest_lng:     Destination longitude
        departure_dt: When the vehicle departs — determines traffic multiplier
        db:           SQLAlchemy session for multiplier lookup

    Returns:
        RouteResult with distance, travel time, and GeoJSON geometry

    Raises:
        NoRouteFound: if no path exists between the two points
    """
    # 1. Get traffic multiplier for origin zone at departure time
    multiplier = get_multiplier_for_location(
        origin_lat, origin_lng, departure_dt, db
    )

    # 2. Apply multiplier to a copy of the graph
    #    (never mutate the cached original)
    G_adjusted = apply_traffic_to_graph(G, multiplier)

    # 3. Snap coordinates to nearest graph nodes
    orig_node = get_nearest_node(G_adjusted, origin_lat, origin_lng)
    dest_node = get_nearest_node(G_adjusted, dest_lat,   dest_lng)

    # 4. Same origin and destination — return zeros
    if orig_node == dest_node:
        return RouteResult(
            origin_lat      = origin_lat,
            origin_lng      = origin_lng,
            dest_lat        = dest_lat,
            dest_lng        = dest_lng,
            distance_m      = 0,
            travel_time_sec = 0,
            geometry        = {"type": "LineString", "coordinates": []},
            multiplier_used = multiplier,
        )

    # 5. Find shortest path by travel_time
    route_nodes = ox.routing.shortest_path(
        G_adjusted, orig_node, dest_node, weight="travel_time"
    )

    if route_nodes is None:
        raise NoRouteFound(
            f"No path between ({origin_lat},{origin_lng}) "
            f"and ({dest_lat},{dest_lng})"
        )

    # 6. Compute metrics from the route GeoDataFrame
    route_gdf       = ox.routing.route_to_gdf(G_adjusted, route_nodes)
    distance_m      = int(route_gdf["length"].sum())
    travel_time_sec = int(route_gdf["travel_time"].sum())

    # 7. Build GeoJSON geometry for storage in Route.geometry
    geometry = route_to_geojson(G_adjusted, route_nodes)

    logger.debug(
        f"Route: {distance_m}m, {travel_time_sec}s "
        f"(multiplier={multiplier}, nodes={len(route_nodes)})"
    )

    return RouteResult(
        origin_lat      = origin_lat,
        origin_lng      = origin_lng,
        dest_lat        = dest_lat,
        dest_lng        = dest_lng,
        distance_m      = distance_m,
        travel_time_sec = travel_time_sec,
        geometry        = geometry,
        multiplier_used = multiplier,
    )