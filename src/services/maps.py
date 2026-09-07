"""
src/services/maps.py

OSMnx graph management service.

Responsibilities:
  1. Load the road network graph for settings.MAP_PLACE (from cache if available)
  2. Cache the graph in Redis so it survives app restarts without re-downloading
  3. Apply traffic multipliers to edge travel times before routing
  4. Expose routing functions used by the optimizer

Graph is loaded ONCE, by the lifespan handler in src/main.py, and held in memory
for the process lifetime. That load is best-effort: if it fails, the first solve
loads it lazily instead (see alns/problem_data.py::_get_graph). Seed Redis with
src.utils.scripts.seed_graph so startup is a fast unpickle rather than a
multi-minute download from OSM.
"""

import pickle
import logging
from datetime import datetime
from typing import Optional
from src.infrastructure.redis.redis import get_redis
import osmnx as ox
import networkx as nx

from src.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OSMnx settings
# ---------------------------------------------------------------------------

ox.settings.use_cache        = True
ox.settings.cache_folder     = "./cache"       # local disk cache for OSM queries
ox.settings.log_console      = False           # silence OSMnx's own logger

# ---------------------------------------------------------------------------
# Redis key
# ---------------------------------------------------------------------------

GRAPH_CACHE_KEY = "karachi:road_graph:v1"
# Bump the version suffix whenever you want to force a graph refresh
# e.g. "karachi:road_graph:v2"
# NOTE: this key does not encode settings.MAP_PLACE. If you change MAP_PLACE,
# bump the version here too, or the old city's graph will be served from cache.

# ---------------------------------------------------------------------------
# Module-level graph singleton
# In a multi-worker setup (Gunicorn/Uvicorn), each worker holds its own copy.
# That's fine — the graph is read-only after loading.
# ---------------------------------------------------------------------------

_graph: Optional[nx.MultiDiGraph] = None

# ---------------------------------------------------------------------------
# Graph loading
# ---------------------------------------------------------------------------

def load_graph(force_reload: bool = False) -> nx.MultiDiGraph:
    """
    Load the Karachi road graph.

    Priority order:
      1. Module-level singleton (already in this process's memory)
      2. Redis cache (pickled graph, survives process restarts)
      3. Local OSMnx disk cache (survives machine restarts, no network needed)
      4. Fresh download from OpenStreetMap (slow, ~2-5 min first time)

    Args:
        force_reload: If True, skip memory + Redis cache and reload from OSM.
                      Use this to pick up OSM map updates.
    """
    global _graph

    if _graph is not None and not force_reload:
        logger.debug("Graph: using in-memory singleton")
        return _graph

    if not force_reload:
        cached = _load_from_redis()
        if cached is not None:
            logger.info("Graph: loaded from Redis cache")
            _graph = cached
            return _graph

    logger.info("Graph: loading from OSMnx (disk cache or fresh download)...")
    _graph = _load_from_osmnx()

    _save_to_redis(_graph)
    logger.info("Graph: saved to Redis cache")

    return _graph


def _load_from_redis() -> Optional[nx.MultiDiGraph]:
    """Try to load the pickled graph from Redis. Returns None on miss/error."""
    try:
        r = get_redis()
        data = r.get(GRAPH_CACHE_KEY)
        if data is None:
            logger.debug("Graph: Redis cache miss")
            return None
        return pickle.loads(data)
    except Exception as e:
        logger.warning(f"Graph: Redis load failed ({e}), falling through")
        return None


def _save_to_redis(G: nx.MultiDiGraph) -> None:
    """Pickle and store the graph in Redis. No TTL — graph is stable."""
    try:
        r = get_redis()
        data = pickle.dumps(G, protocol=pickle.HIGHEST_PROTOCOL)
        r.set(GRAPH_CACHE_KEY, data)
        size_mb = len(data) / (1024 * 1024)
        logger.info(f"Graph: stored in Redis ({size_mb:.1f} MB)")
    except Exception as e:
        logger.warning(f"Graph: Redis save failed ({e}), continuing without cache")


def _load_from_osmnx() -> nx.MultiDiGraph:
    """
    Download (or load from OSMnx disk cache) the drive network for
    settings.MAP_PLACE. Adds speed and travel_time attributes to every edge.

    The place name is shared with src/services/boundary.py, which resolves it to
    the polygon the geocoder filters on — so the search box and the router
    always describe the same city.
    """
    G = ox.graph_from_place(settings.MAP_PLACE, network_type="drive")
    G = ox.routing.add_edge_speeds(G)
    G = ox.routing.add_edge_travel_times(G)
    return G


# ---------------------------------------------------------------------------
# Traffic-weighted travel time
# ---------------------------------------------------------------------------

def get_traffic_multiplier(
    h3_index: str,
    dt: datetime,
    db_session,                  # SQLAlchemy Session
) -> float:
    """
    Look up the traffic multiplier for a given H3 zone at a given datetime.

    Returns 1.0 (no adjustment) if no profile is found — safe default.

    Args:
        h3_index:   Resolution-9 H3 index of the location
        dt:         The datetime we want the multiplier for
        db_session: SQLAlchemy session (injected by caller)
    """
    from src.services.h3_service import location_to_zone
    from src.db.models import TrafficProfile, DayType

    zone_index = location_to_zone(h3_index)   # res-9 → res-8
    hour       = dt.hour
    day_type   = _get_day_type(dt)

    profile = (
        db_session.query(TrafficProfile)
        .filter(
            TrafficProfile.h3_index   == zone_index,
            TrafficProfile.day_type   == day_type,
            TrafficProfile.hour_start <= hour,
            TrafficProfile.hour_end   >= hour,
        )
        .first()
    )

    if profile is None:
        return 1.0   # free-flow fallback

    return float(profile.multiplier)


def _get_day_type(dt: datetime):
    """Map a datetime to a DayType enum value."""
    from src.core.enums import DayType

    weekday = dt.weekday()   # 0=Monday … 6=Sunday
    if weekday == 4:         # Friday — important in Karachi (Jumu'ah traffic)
        return DayType.friday
    elif weekday == 5:
        return DayType.saturday
    elif weekday == 6:
        return DayType.sunday
    else:
        return DayType.weekday


def apply_traffic_to_graph(
    G: nx.MultiDiGraph,
    multiplier: float,
) -> nx.MultiDiGraph:
    
    G_copy = G.copy()
    for u, v, k, data in G_copy.edges(keys=True, data=True):
        if "travel_time" in data:
            G_copy[u][v][k]["travel_time"] = data["travel_time"] * multiplier
    return G_copy


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------

def get_nearest_node(G: nx.MultiDiGraph, lat: float, lng: float) -> int:
    """Snap a lat/lng coordinate to the nearest graph node."""
    return ox.nearest_nodes(G, X=lng, Y=lat)


def peek_graph() -> Optional[nx.MultiDiGraph]:
    """
    The graph if it is ALREADY in this process's memory, else None.

    Deliberately never loads: callers are latency-sensitive paths (the geocode
    autocomplete) that would rather skip a check than block a keystroke on a
    multi-minute OSM download.
    """
    return _graph


# KD-tree over the graph's nodes, built once and reused.
#
# ox.nearest_nodes() rebuilds this tree on EVERY call, which costs ~0.28s
# against Karachi's 178k nodes. The geocode endpoint checks a whole page of
# results per keystroke, so that is ~2.2s of pure tree-building per search.
# The graph is read-only after loading, so the tree can simply be cached.
_node_tree = None
_node_coords: Optional[list] = None


def _get_node_tree(G: nx.MultiDiGraph):
    """(cKDTree, node_ids) over the graph's nodes, built on first use."""
    global _node_tree, _node_coords
    if _node_tree is None:
        import numpy as np
        from scipy.spatial import cKDTree

        node_ids = list(G.nodes)
        coords = np.array([[G.nodes[n]["y"], G.nodes[n]["x"]] for n in node_ids])
        _node_tree = cKDTree(coords)
        _node_coords = (node_ids, coords)
    return _node_tree, _node_coords


def snap_distance_m(G: nx.MultiDiGraph, lat: float, lng: float) -> float:
    """
    Metres from (lat, lng) to the nearest drivable node in the graph.

    A large value means the matrix builder will snap this location to a road far
    away — or fail to route it at all, which surfaces as PENALTY_SEC for every
    pair and an order the solver silently leaves unserved. Checking here turns
    that into a warning at data-entry time.

    The KD-tree query is in degrees (fine for ranking nearby candidates); the
    winner is then measured properly with a great-circle distance in metres.
    """
    tree, (node_ids, coords) = _get_node_tree(G)
    _, idx = tree.query([lat, lng], k=1)
    nlat, nlng = coords[idx]
    return float(ox.distance.great_circle(lat, lng, nlat, nlng))


def shortest_path_by_time(
    G: nx.MultiDiGraph,
    orig_lat: float, orig_lng: float,
    dest_lat: float, dest_lng: float,
) -> tuple:
    """
    Find the fastest path between two coordinates.

    Returns:
        (route_nodes, distance_m, travel_time_sec)
        route_nodes: list of OSMnx node IDs along the path
    """
    orig_node = get_nearest_node(G, orig_lat, orig_lng)
    dest_node = get_nearest_node(G, dest_lat, dest_lng)

    route = ox.routing.shortest_path(G, orig_node, dest_node, weight="travel_time")

    if route is None:
        raise ValueError(
            f"No path found between ({orig_lat},{orig_lng}) and ({dest_lat},{dest_lng})"
        )

    route_gdf         = ox.routing.route_to_gdf(G, route)
    distance_m        = int(route_gdf["length"].sum())
    travel_time_sec   = int(route_gdf["travel_time"].sum())

    return route, distance_m, travel_time_sec


def route_to_geojson(G: nx.MultiDiGraph, route_nodes: list) -> dict:
    """
    Convert a list of route node IDs to a GeoJSON LineString.
    Stored in Route.geometry for map rendering.
    """
    route_gdf = ox.routing.route_to_gdf(G, route_nodes)
    # dissolve all edges into a single LineString
    dissolved  = route_gdf.dissolve()
    geojson    = dissolved.geometry.iloc[0].__geo_interface__
    return geojson