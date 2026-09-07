"""
src/services/photon.py

Photon geocoding client — turns a typed address into coordinates.

Photon (https://github.com/komoot/photon) is a search-as-you-type geocoder over
OSM data. It is built to be hit on every keystroke, which shapes this module:
responses are small, cached in Redis, and every failure mode degrades to an
empty result list rather than an exception the dropdown cannot render.

By default this talks to Komoot's free public instance. There is no API key and
no published quota; Komoot ask that you not bulk-geocode. The client debounces
so most keystrokes never reach here, and _search_photon caches what does.

Karachi-only is enforced twice, by src/services/boundary.py:
  * ``bbox`` on the request  — Photon filters server-side. Verified to be a HARD
    filter, not a bias: with the Karachi bbox, "eiffel tower" returns only
    Bahria Town's replica and "lahore" returns no Lahore results at all.
  * ``is_inside`` on the response — the exact polygon, because a bbox around
    Karachi Division is ~3x the polygon's area (mostly sea and desert).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

import requests

from src.core.config import settings
from src.services import boundary

logger = logging.getLogger(__name__)

# Bump to invalidate every cached search (e.g. after changing the label format).
_CACHE_VERSION = "v1"


# ---------------------------------------------------------------------------
# Label composition
# ---------------------------------------------------------------------------

def _primary_label(props: dict[str, Any]) -> str:
    """
    The bold first line of a dropdown row: what the dispatcher actually scans.

    Prefers the POI/street ``name``, falling back to "housenumber street" for
    plain addresses, then to whatever single field exists. Photon omits fields
    rather than nulling them, so every access is a .get().
    """
    name = props.get("name")
    if name:
        return str(name)

    housenumber, street = props.get("housenumber"), props.get("street")
    if housenumber and street:
        return f"{housenumber} {street}"
    if street:
        return str(street)

    # Last resort: an administrative feature with no name of its own.
    for key in ("locality", "district", "city"):
        if props.get(key):
            return str(props[key])
    return "Unnamed location"


def _secondary_label(props: dict[str, Any], primary: str) -> str:
    """
    The muted second line: where in the city this is.

    ``city`` is deliberately excluded — every result is inside the service area
    by construction, so repeating "Karachi" on every row is noise. That also
    dodges most of the mixed-script problem: Karachi's admin boundaries are
    frequently tagged in Urdu (city="کراچی", district="گلشن اقبال") while
    ``name`` and ``street`` are far more often Latin.

    ``street`` leads when it is not already the primary line, so a POI shows the
    road it sits on.
    """
    parts: list[str] = []
    for key in ("street", "locality", "district"):
        val = props.get(key)
        if not val:
            continue
        val = str(val)
        # Skip anything already visible in the primary line, and de-dupe
        # locality/district when OSM tags them identically.
        if val == primary or val in parts or val in primary:
            continue
        parts.append(val)
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Feature normalisation
# ---------------------------------------------------------------------------

def _feature_to_result(feature: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Flatten one Photon GeoJSON feature into the shape the frontend consumes.

    Returns None for anything unusable — a feature with no point geometry, or
    one outside the service-area polygon. Photon's schema is loose enough that
    defensive parsing here is cheaper than validation downstream.
    """
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates")
    # GeoJSON is [lng, lat] — the reverse of every other coordinate in this
    # codebase, which is a classic source of silently-transposed points.
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return None
    try:
        lng, lat = float(coords[0]), float(coords[1])
    except (TypeError, ValueError):
        return None

    if not boundary.is_inside(lat, lng):
        return None

    props = feature.get("properties") or {}
    primary = _primary_label(props)
    return {
        "label":     primary,
        "context":   _secondary_label(props, primary),
        "lat":       lat,
        "lng":       lng,
        "type":      props.get("type"),
        "osm_id":    props.get("osm_id"),
        "osm_type":  props.get("osm_type"),
        "postcode":  props.get("postcode"),
    }


def _address_text(result: dict[str, Any]) -> str:
    """The single string persisted to Location.address_text."""
    return ", ".join(p for p in (result["label"], result["context"]) if p)


# ---------------------------------------------------------------------------
# Photon HTTP
# ---------------------------------------------------------------------------

def _cache_key(query: str, limit: int) -> str:
    digest = hashlib.sha1(f"{query}|{limit}|{settings.MAP_PLACE}".encode("utf-8")).hexdigest()[:16]
    return f"geocode:{_CACHE_VERSION}:{digest}"


def _cached_get(key: str) -> Optional[list[dict[str, Any]]]:
    try:
        from src.infrastructure.redis.redis import get_redis
        raw = get_redis().get(key)
        return json.loads(raw) if raw is not None else None
    except Exception:
        return None      # cache failure is never fatal


def _cached_set(key: str, value: list[dict[str, Any]]) -> None:
    try:
        from src.infrastructure.redis.redis import get_redis
        get_redis().setex(key, settings.GEOCODE_CACHE_TTL_SEC, json.dumps(value))
    except Exception:
        pass


def search(query: str, limit: Optional[int] = None) -> list[dict[str, Any]]:
    """
    Search the service area for ``query``.

    Returns a list of normalised results (possibly empty). Never raises for
    network or upstream problems: an autocomplete that 500s on a slow response
    is worse than one that shows nothing for a keystroke.
    """
    query = (query or "").strip()
    if not query:
        return []

    limit = limit or settings.GEOCODE_RESULT_LIMIT
    key = _cache_key(query.lower(), limit)

    cached = _cached_get(key)
    if cached is not None:
        return cached

    params: dict[str, Any] = {
        "q": query,
        # Over-fetch: the polygon filter below discards some of what the looser
        # bbox lets through, and we still want a full dropdown afterwards.
        "limit": limit * 2,
        # Prefer English names where OSM has them. Karachi is inconsistently
        # tagged, so this helps but does not guarantee Latin script.
        "lang": "en",
    }

    bbox = boundary.get_bbox_or_none()
    if bbox:
        params["bbox"] = ",".join(f"{v:.6f}" for v in bbox)

    center = boundary.get_center()
    if center:
        # Soft distance bias — reranks, never excludes. Pushes city-centre hits
        # above equally-good matches at the edge of the service area.
        params["lat"], params["lon"] = center

    try:
        resp = requests.get(
            f"{settings.PHOTON_BASE_URL.rstrip('/')}/api",
            params=params,
            timeout=settings.PHOTON_TIMEOUT_SEC,
            headers={"User-Agent": "logistics-management/0.1 (dispatch console)"},
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.Timeout:
        logger.warning(f"Photon: timed out after {settings.PHOTON_TIMEOUT_SEC}s for {query!r}")
        return []
    except requests.RequestException as e:
        logger.warning(f"Photon: request failed for {query!r} ({e})")
        return []
    except ValueError as e:
        logger.warning(f"Photon: malformed JSON for {query!r} ({e})")
        return []

    results: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for feature in (payload.get("features") or []):
        result = _feature_to_result(feature)
        if result is None:
            continue
        # OSM frequently holds the same place as both a node and a way; dedupe
        # on rounded coordinates (~1m) so the dropdown does not show doubles.
        fingerprint = (result["label"], round(result["lat"], 5), round(result["lng"], 5))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        result["address_text"] = _address_text(result)
        results.append(result)
        if len(results) >= limit:
            break

    _cached_set(key, results)
    return results
