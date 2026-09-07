"""
src/api/v1/geocode.py

Address search for the dispatch console — type an address, get coordinates,
instead of hand-entering lat/lng decimals.

The frontend calls THIS, never photon.komoot.io directly. That keeps the
service-area filter server-side where no client can bypass it, keeps every call
inside the existing Bearer-token flow, gives one place to cache, and makes
swapping in a self-hosted Photon a config change.

Results are advisory: this endpoint writes nothing. The caller takes the lat/lng
and address_text it picks and POSTs them to /v1/orders (or customers/depots)
exactly as if they had been typed by hand, so nothing downstream — H3 indexing,
the matrix builder, ALNS — changes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from src.api.v1.deps import get_current_user, CurrentUser
from src.core.config import settings
from src.schemas.geocode import GeocodeResult, GeocodeSearchOut
from src.services import photon

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/geocode", tags=["geocode"])


def _annotate_routability(results: list[dict]) -> None:
    """
    Tag each result with how far it sits from the nearest drivable road.

    Uses the graph only if it is already in memory (see maps.peek_graph) — an
    autocomplete must not trigger a multi-minute OSM download. When it is
    missing, routable stays None and the console simply shows no warning.
    """
    from src.services.maps import peek_graph, snap_distance_m

    G = peek_graph()
    if G is None:
        return

    for r in results:
        try:
            d = snap_distance_m(G, r["lat"], r["lng"])
            r["snap_distance_m"] = round(d, 1)
            r["routable"] = d <= settings.GEOCODE_MAX_SNAP_M
        except Exception as e:
            # A snap failure is not a reason to drop an otherwise good result.
            logger.debug(f"Geocode: snap check failed for {r.get('label')!r} ({e})")


@router.get("/search", response_model=GeocodeSearchOut)
def search_addresses(
    q: str = Query(..., min_length=2, max_length=200,
                   description="Partial address or place name."),
    limit: int = Query(default=0, ge=0, le=20,
                       description="Max results; 0 uses the server default."),
    current: CurrentUser = Depends(get_current_user),
):
    """
    Search the service area for an address.

    Called on every (debounced) keystroke, so it is deliberately forgiving:
    upstream failures return an empty list rather than an error, leaving the
    dispatcher free to fall back to manual coordinate entry.
    """
    results = photon.search(q, limit=limit or None)
    _annotate_routability(results)
    return GeocodeSearchOut(
        query=q,
        results=[GeocodeResult(**r) for r in results],
    )
