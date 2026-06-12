import json
import logging
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple, Optional

import networkx as nx
from sqlalchemy.orm import Session

from src.services.routing import (
    route_between,
    get_multiplier_for_location,
    _get_day_type,
)
from src.services.maps import apply_traffic_to_graph
from src.infrastructure.redis.redis import _cache_key, _get_cached, _set_cached
from src.exceptions.routing import NoRouteFound
from src.core.config import settings
from src.schemas.matrix import Location, MatrixResult

logger = logging.getLogger(__name__)

def build_matrix(
    locations:    List[Location],
    departure_dt: datetime,
    G:            nx.MultiDiGraph,
    db:           Session,
) -> MatrixResult:

    n = len(locations)
    if n < 2:
        raise ValueError("Need at least 2 locations (depot + 1 stop)")

    depot     = locations[0]
    day_type  = _get_day_type(departure_dt)
    hour      = departure_dt.hour

    multiplier = get_multiplier_for_location(
        depot.lat, depot.lng, departure_dt, db
    )
    logger.info(
        f"Matrix build: {n} locations, "
        f"departure={departure_dt.strftime('%a %H:%M')}, "
        f"multiplier={multiplier:.2f}"
    )

    # ── Apply multiplier ONCE to graph copy ───────────────────────────────
    # Much cheaper than copying inside route_between() N² times.
    G_adjusted = apply_traffic_to_graph(G, multiplier)

    # ── Build empty matrix ────────────────────────────────────────────────
    matrix: List[List[int]] = [[0] * n for _ in range(n)]

    cache_hits = 0
    computed   = 0
    failed     = 0

    total_pairs = n * (n - 1)     # diagonal stays 0
    done        = 0

    for i in range(n):
        for j in range(n):
            if i == j:
                continue          # diagonal is always 0

            origin = locations[i]
            dest   = locations[j]

            # ── Cache lookup ──────────────────────────────────────────────
            key    = _cache_key(
                origin.lat, origin.lng,
                dest.lat,   dest.lng,
                day_type.value, hour,
            )
            cached = _get_cached(key)

            if cached is not None:
                matrix[i][j] = cached
                cache_hits   += 1
                done         += 1
                continue

            # ── Fresh computation ─────────────────────────────────────────
            try:
                # Pass the already-adjusted graph and multiplier=1.0
                # so route_between doesn't re-apply any multiplier.
                # We monkey-patch departure_dt to a fixed hour so the
                # internal multiplier lookup inside route_between returns 1.0
                # (since we already baked it into G_adjusted).
                result = _route_on_adjusted_graph(
                    G_adjusted, origin, dest, departure_dt, db
                )
                travel_time_sec  = result
                matrix[i][j]     = travel_time_sec
                _set_cached(key, travel_time_sec)
                computed += 1

            except NoRouteFound:
                logger.warning(
                    f"No route: {origin.label}({origin.lat},{origin.lng}) → "
                    f"{dest.label}({dest.lat},{dest.lng}) — using penalty"
                )
                matrix[i][j] = settings.PENALTY_SEC
                failed       += 1

            done += 1
            if done % 50 == 0 or done == total_pairs:
                pct = int(done / total_pairs * 100)
                logger.info(f"  Matrix progress: {done}/{total_pairs} pairs ({pct}%)")

    result = MatrixResult(
        matrix     = matrix,
        locations  = locations,
        multiplier = multiplier,
        cache_hits = cache_hits,
        computed   = computed,
        failed     = failed,
    )
    logger.info(f"Matrix complete: {result.summary()}")
    return result


# ---------------------------------------------------------------------------
# Internal routing on pre-adjusted graph
# ---------------------------------------------------------------------------

def _route_on_adjusted_graph(
    G_adjusted:   nx.MultiDiGraph,
    origin:       Location,
    dest:         Location,
    departure_dt: datetime,
    db:           Session,
) -> int:
    """
    Run shortest path on an already traffic-adjusted graph.
    Returns travel_time_sec.
    Raises NoRouteFound if no path exists.

    We import osmnx here directly rather than going through route_between()
    because route_between() would re-apply traffic (we already did it).
    """
    import osmnx as ox

    orig_node = ox.nearest_nodes(G_adjusted, X=origin.lng, Y=origin.lat)
    dest_node = ox.nearest_nodes(G_adjusted, X=dest.lng,   Y=dest.lat)

    if orig_node == dest_node:
        return 0

    route_nodes = ox.routing.shortest_path(
        G_adjusted, orig_node, dest_node, weight="travel_time"
    )

    if route_nodes is None:
        raise NoRouteFound(
            f"No path: ({origin.lat},{origin.lng}) → ({dest.lat},{dest.lng})"
        )

    route_gdf       = ox.routing.route_to_gdf(G_adjusted, route_nodes)
    travel_time_sec = int(route_gdf["travel_time"].sum())
    return travel_time_sec