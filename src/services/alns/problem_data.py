"""
src/services/alns/problem_data.py

Loads a routing instance from the DB (or a synthetic source) into an immutable,
in-memory ``ProblemData`` object that the ALNS loop reads from without ever
touching the DB or the road graph mid-search.

Design notes
------------
* ``ProblemData`` is treated as read-only shared reference during the ALNS
  search (plan Section 4). Only the mutable solution state is copied per
  iteration; this object never is.

* Travel time is a **per-hour matrix stack**: ``travel_time[hour][i][j]`` in
  seconds, where ``i``/``j`` are *node indices* into ``self.nodes`` (depot +
  order locations). ``hour`` is the departure hour bucket (0-23). This keeps
  time-of-day traffic variation without calling OSMnx inside the objective.

* Distances are traffic-independent, so we compute the distance matrix **once**
  and only re-scale travel times per hour. That keeps the per-hour stack cheap.

* Travel time is sourced through a pluggable ``TravelTimeProvider`` so the same
  ProblemData shape works for real DB loads (OSMnx road graph, Redis-cached)
  and fast synthetic instances (haversine / avg speed).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.enums import ServiceType, DayType


# ---------------------------------------------------------------------------
# Lightweight value types (plain data, no ORM identity, safe to share)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NodeRef:
    """A point in the routing graph: the depot or an order's service location."""
    index: int            # position in ProblemData.nodes / matrix axis
    location_id: int
    lat: float
    lng: float
    h3_index: str
    is_depot: bool = False
    order_id: Optional[int] = None   # None for the depot node
    # res-POOL_H3_RESOLUTION cell of this point, computed live from lat/lng (the
    # stored Location.h3_index may be a synthetic placeholder). Used as the
    # ride-pooling bucket key: same zone_h3 = "same area" for shared shuttle legs.
    zone_h3: Optional[str] = None


@dataclass(frozen=True)
class OrderInfo:
    id: int
    node_index: int                  # index into ProblemData.nodes
    required_skills: frozenset[str]  # skill enum values (from whichever column applies)
    timewindow_start: Optional[datetime]
    timewindow_end: Optional[datetime]
    service_duration_sec: int
    priority: str
    weight_kg: float
    volume_m3: float


@dataclass(frozen=True)
class WorkerInfo:
    id: int
    worker_type: ServiceType
    skills: frozenset[str]
    shift_start: Optional[time]
    shift_end: Optional[time]


@dataclass(frozen=True)
class VehicleInfo:
    id: int
    vehicle_type: str                # VehicleType value
    seating_capacity: int
    avg_speed_kmh: float
    fuel_type: str
    fuel_average: float              # litres (or kWh) per km
    fuel_price: float                # PKR per litre/kWh, resolved from config


@dataclass(frozen=True)
class DriverInfo:
    id: int
    vehicle_id: Optional[int]
    eligible_vehicle_types: frozenset[str]   # Driver.skills = ARRAY(VehicleType)


# ---------------------------------------------------------------------------
# Travel-time providers (pluggable)
# ---------------------------------------------------------------------------

class TravelTimeProvider:
    """
    Produces a distance matrix and a per-hour traffic multiplier for a set of
    nodes. ProblemData combines these into the per-hour travel-time stack.
    """

    def distance_matrix(self, nodes: Sequence[NodeRef]) -> list[list[float]]:
        """Return distances in metres, distance[i][j]. Diagonal = 0."""
        raise NotImplementedError

    def base_travel_time(self, nodes: Sequence[NodeRef]) -> list[list[float]]:
        """
        Return free-flow (multiplier=1.0) travel time in seconds, time[i][j].
        Per-hour times are this scaled by the hour's traffic multiplier.
        """
        raise NotImplementedError

    def hour_multiplier(self, node: NodeRef, day_type: DayType, hour: int) -> float:
        """Traffic multiplier for a node's zone at a given day_type + hour."""
        raise NotImplementedError


class HaversineProvider(TravelTimeProvider):
    """
    Fast, road-graph-free provider for synthetic instances and unit tests.

    Distance = great-circle (haversine). Travel time = distance / avg_speed.
    Traffic multiplier is a caller-supplied callable (defaults to free-flow
    1.0), so synthetic tests can inject deterministic traffic patterns.
    """

    def __init__(self, avg_speed_kmh: float = 40.0, multiplier_fn=None):
        self.avg_speed_kmh = avg_speed_kmh
        # multiplier_fn(node, day_type, hour) -> float; default free-flow
        self._multiplier_fn = multiplier_fn or (lambda node, day_type, hour: 1.0)

    @staticmethod
    def _haversine_m(lat1, lng1, lat2, lng2) -> float:
        R = 6_371_000.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlmb = math.radians(lng2 - lng1)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
        return 2 * R * math.asin(math.sqrt(a))

    def distance_matrix(self, nodes: Sequence[NodeRef]) -> list[list[float]]:
        n = len(nodes)
        m = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                m[i][j] = self._haversine_m(
                    nodes[i].lat, nodes[i].lng, nodes[j].lat, nodes[j].lng
                )
        return m

    def base_travel_time(self, nodes: Sequence[NodeRef]) -> list[list[float]]:
        dist = self.distance_matrix(nodes)
        speed_m_s = self.avg_speed_kmh * 1000.0 / 3600.0
        n = len(nodes)
        return [
            [0.0 if i == j else dist[i][j] / speed_m_s for j in range(n)]
            for i in range(n)
        ]

    def hour_multiplier(self, node: NodeRef, day_type: DayType, hour: int) -> float:
        return float(self._multiplier_fn(node, day_type, hour))


class OSMnxProvider(TravelTimeProvider):
    """
    Real-road provider for DB-backed loads. Wraps the existing OSMnx-based
    matrix + traffic-multiplier services. Heavier (routes per pair, cached in
    Redis) — intended for background solves, not tight unit-test loops.
    """

    def __init__(self, db: Session, graph=None):
        self.db = db
        self._graph = graph  # lazily loaded if None
        # cache filled by the first _build pass; reused for base_travel_time /
        # distance_matrix and, importantly, for road GEOMETRY at persist time so
        # each pair is routed exactly once.
        self._time_m = None
        self._dist_m = None
        self._geometry = {}   # (i, j) -> GeoJSON LineString for the leg

    def _get_graph(self):
        if self._graph is None:
            from src.services.maps import load_graph
            self._graph = load_graph()   # may raise -> caller handles infra fallback
        return self._graph

    def distance_matrix(self, nodes: Sequence[NodeRef]) -> list[list[float]]:
        self._ensure_built(nodes)
        return self._dist_m

    def base_travel_time(self, nodes: Sequence[NodeRef]) -> list[list[float]]:
        self._ensure_built(nodes)
        return self._time_m

    def leg_geometry(self, i: int, j: int) -> Optional[dict]:
        """Road-following GeoJSON LineString for node i -> j (or None if same node)."""
        return self._geometry.get((i, j))

    def _ensure_built(self, nodes: Sequence[NodeRef]):
        if self._time_m is None:
            self._time_m, self._dist_m = self._build_time_and_distance(nodes)

    def _build_time_and_distance(self, nodes: Sequence[NodeRef]):
        """
        Build free-flow time + distance matrices (and per-leg geometry) via OSMnx
        shortest paths. Each pair is routed ONCE — ProblemData applies per-hour
        traffic multipliers on top (geometry/distance don't change by hour).

        Hard-fails with LocationUnroutable if a node can't snap or a pair can't
        be routed: that's a DATA problem worth surfacing, not silently penalizing.
        (Whole-graph load failure is handled by the caller as an infra fallback.)
        """
        from src.services.maps import get_nearest_node, apply_traffic_to_graph, route_to_geojson
        from src.exceptions.routing import LocationUnroutable
        import osmnx as ox

        # free-flow graph (multiplier 1.0 baseline)
        G = apply_traffic_to_graph(self._get_graph(), 1.0)

        # snap every node to the nearest graph node. A snap that raises is an
        # infra/tooling problem (e.g. missing spatial-search dependency) — let it
        # propagate as a generic solve failure. A snap that returns nothing usable
        # would surface as a routing failure below (LocationUnroutable = bad data).
        snapped = [get_nearest_node(G, nd.lat, nd.lng) for nd in nodes]

        n = len(nodes)
        time_m = [[0.0] * n for _ in range(n)]
        dist_m = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j or snapped[i] == snapped[j]:
                    continue
                route = ox.routing.shortest_path(
                    G, snapped[i], snapped[j], weight="travel_time"
                )
                if route is None:
                    raise LocationUnroutable(
                        nodes[j].lat, nodes[j].lng,
                        f"no road path from ({nodes[i].lat},{nodes[i].lng})",
                    )
                gdf = ox.routing.route_to_gdf(G, route)
                time_m[i][j] = float(gdf["travel_time"].sum())
                dist_m[i][j] = float(gdf["length"].sum())
                self._geometry[(i, j)] = route_to_geojson(G, route)
        return time_m, dist_m

    def hour_multiplier(self, node: NodeRef, day_type: DayType, hour: int) -> float:
        from src.services.routing import get_multiplier_for_location
        # get_multiplier_for_location keys off the location's zone + hour;
        # we pass a datetime whose hour drives the lookup.
        probe = datetime.combine(date.today(), time(hour=hour))
        return get_multiplier_for_location(node.lat, node.lng, probe, self.db)


# ---------------------------------------------------------------------------
# ProblemData
# ---------------------------------------------------------------------------

@dataclass
class ProblemData:
    """
    Immutable, in-memory routing instance. Shared read-only across the ALNS
    search — never copied per iteration.
    """
    company_id: int
    planned_date: date
    service_type: ServiceType
    day_type: DayType

    nodes: list[NodeRef]                       # index 0 is the depot
    depot_node_index: int

    orders: list[OrderInfo]
    workers: list[WorkerInfo]
    drivers: list[DriverInfo]
    vehicles: list[VehicleInfo]

    # per-hour travel-time stack: travel_time_sec[hour][i][j], hour in 0..23
    travel_time_sec: dict[int, list[list[float]]]
    distance_m: list[list[float]]              # traffic-independent, shared

    active_hours: tuple[int, ...]              # hours the stack was built for

    # optional geometry source: the provider that routed the legs, so persistence
    # can fetch real road geometry per leg. None for Haversine (straight lines).
    geometry_source: object = None

    # convenience lookups
    order_by_id: dict[int, OrderInfo] = field(default_factory=dict)
    worker_by_id: dict[int, WorkerInfo] = field(default_factory=dict)
    vehicle_by_id: dict[int, VehicleInfo] = field(default_factory=dict)
    driver_by_id: dict[int, DriverInfo] = field(default_factory=dict)

    def __post_init__(self):
        self.order_by_id = {o.id: o for o in self.orders}
        self.worker_by_id = {w.id: w for w in self.workers}
        self.vehicle_by_id = {v.id: v for v in self.vehicles}
        self.driver_by_id = {d.id: d for d in self.drivers}

    # ---- travel-time access -------------------------------------------------

    def _clamp_hour(self, hour: int) -> int:
        """Snap a departure hour to the nearest built active hour."""
        if hour in self.travel_time_sec:
            return hour
        return min(self.active_hours, key=lambda h: abs(h - hour))

    def travel_time(self, i: int, j: int, hour: int) -> float:
        """Traffic-adjusted travel time (sec) between node i and node j at `hour`."""
        return self.travel_time_sec[self._clamp_hour(hour)][i][j]

    def distance(self, i: int, j: int) -> float:
        """Distance (metres) between node i and node j (traffic-independent)."""
        return self.distance_m[i][j]

    # ---- feasibility helpers ------------------------------------------------

    def worker_can_serve(self, worker_id: int, order_id: int) -> bool:
        """A worker can serve an order iff they hold all its required skills."""
        w = self.worker_by_id[worker_id]
        o = self.order_by_id[order_id]
        if not o.required_skills:
            return True
        return o.required_skills.issubset(w.skills)

    def driver_can_drive(self, driver_id: int, vehicle_id: int) -> bool:
        """A driver can operate a vehicle iff its type is in their eligible set."""
        d = self.driver_by_id[driver_id]
        v = self.vehicle_by_id[vehicle_id]
        if not d.eligible_vehicle_types:
            return True   # unspecified skills => unrestricted
        return v.vehicle_type in d.eligible_vehicle_types


# ---------------------------------------------------------------------------
# Day-type helper (mirrors services.routing._get_day_type; kept local so the
# loader has no import cycle with routing when using the haversine provider)
# ---------------------------------------------------------------------------

def day_type_for(d: date) -> DayType:
    wd = d.weekday()   # 0=Mon .. 6=Sun
    if wd == 4:
        return DayType.friday
    if wd == 5:
        return DayType.saturday
    if wd == 6:
        return DayType.sunday
    return DayType.weekday


def _pool_zone(lat: float, lng: float) -> Optional[str]:
    """
    Real res-POOL_H3_RESOLUTION H3 cell for a point, computed live from lat/lng
    (the stored Location.h3_index may be a synthetic placeholder, so we never
    trust it here). This is the ride-pooling bucket key. Returns None on failure
    so pooling just falls back to per-worker legs rather than crashing.
    """
    try:
        from src.services.h3_service import latlng_to_h3
        return latlng_to_h3(lat, lng, resolution=settings.POOL_H3_RESOLUTION)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Stack builder
# ---------------------------------------------------------------------------

def build_travel_stack(
    nodes: list[NodeRef],
    provider: TravelTimeProvider,
    day_type: DayType,
    active_hours: Sequence[int],
) -> tuple[dict[int, list[list[float]]], list[list[float]]]:
    """
    Build the per-hour travel-time stack + shared distance matrix.

    Distance and base (free-flow) time are computed once. For each active hour,
    base time is scaled by that hour's per-origin traffic multiplier.
    """
    distance = provider.distance_matrix(nodes)
    base_time = provider.base_travel_time(nodes)
    n = len(nodes)

    stack: dict[int, list[list[float]]] = {}
    for hour in active_hours:
        # multiplier is per origin node (traffic where the leg starts)
        origin_mult = [provider.hour_multiplier(nodes[i], day_type, hour) for i in range(n)]
        stack[hour] = [
            [0.0 if i == j else base_time[i][j] * origin_mult[i] for j in range(n)]
            for i in range(n)
        ]
    return stack, distance


# ---------------------------------------------------------------------------
# DB loader
# ---------------------------------------------------------------------------

def load_problem_data(
    db: Session,
    company_id: int,
    planned_date: date,
    provider: Optional[TravelTimeProvider] = None,
    active_hours: Optional[Sequence[int]] = None,
    order_ids: Optional[Sequence[int]] = None,
) -> ProblemData:
    """
    Load a single-company, single-day routing instance from the DB.

    Uses ``Company.service_type`` to decide whether to load nurses or
    technicians and which order skill-column to read.

    Order selection (single-day by construction):
      * only servable orders are loaded — status in (pending, assigned)
      * scoped to the plan's day — Order.service_date == planned_date
      * if ``order_ids`` is given, restrict to exactly those (after the above
        filters still apply). Callers that need strict validation of the IDs
        (wrong company / non-servable / wrong date) should validate upstream;
        the loader simply won't include anything that fails the filters.
    """
    from src.db.models import (
        Company, Depot, Location, Order, Vehicle, Driver, Nurse, Technician, Employee,
    )
    from src.core.enums import OrderStatus

    SERVABLE_STATUSES = (OrderStatus.pending, OrderStatus.assigned)

    company = db.query(Company).filter(Company.id == company_id).one()
    if company.service_type is None:
        raise ValueError(
            f"Company {company_id} has no service_type set; cannot determine "
            f"whether to load nurses or technicians."
        )
    service_type = company.service_type
    dtype = day_type_for(planned_date)

    depot = (
        db.query(Depot)
        .filter(Depot.company_id == company_id)
        .order_by(Depot.id)
        .first()
    )
    if depot is None or depot.location_id is None:
        raise ValueError(f"Company {company_id} has no depot with a location.")
    depot_loc = db.query(Location).filter(Location.id == depot.location_id).one()

    # ---- nodes: depot first, then one per order location --------------------
    order_query = (
        db.query(Order)
        .filter(
            Order.company_id == company_id,
            Order.location_id.isnot(None),
            Order.status.in_(SERVABLE_STATUSES),
            Order.service_date == planned_date,
        )
    )
    if order_ids is not None:
        order_query = order_query.filter(Order.id.in_(list(order_ids)))
    orders_q = order_query.order_by(Order.id).all()

    nodes: list[NodeRef] = [
        NodeRef(
            index=0, location_id=depot_loc.id, lat=depot_loc.lat, lng=depot_loc.lng,
            h3_index=depot_loc.h3_index, is_depot=True, order_id=None,
            zone_h3=_pool_zone(depot_loc.lat, depot_loc.lng),
        )
    ]
    order_infos: list[OrderInfo] = []
    loc_cache: dict[int, Location] = {}
    for o in orders_q:
        loc = loc_cache.get(o.location_id)
        if loc is None:
            loc = db.query(Location).filter(Location.id == o.location_id).one()
            loc_cache[o.location_id] = loc
        idx = len(nodes)
        nodes.append(NodeRef(
            index=idx, location_id=loc.id, lat=loc.lat, lng=loc.lng,
            h3_index=loc.h3_index, is_depot=False, order_id=o.id,
            zone_h3=_pool_zone(loc.lat, loc.lng),
        ))

        if service_type == ServiceType.nurse:
            raw_skills = o.required_nurse_skills or []
        else:
            raw_skills = o.required_tech_skills or []
        skills = frozenset(s.value if hasattr(s, "value") else str(s) for s in raw_skills)

        dur_min = o.service_duration_min or settings.DEFAULT_SERVICE_DURATION_MIN
        order_infos.append(OrderInfo(
            id=o.id, node_index=idx, required_skills=skills,
            timewindow_start=o.timewindow_start, timewindow_end=o.timewindow_end,
            service_duration_sec=int(dur_min) * 60,
            priority=o.priority.value if o.priority else "normal",
            weight_kg=float(o.weight_kg or 0), volume_m3=float(o.volume_m3 or 0),
        ))

    # ---- workers (nurses or technicians) ------------------------------------
    # Only ACTIVE workers are eligible for NEW plans — a worker who marked
    # themselves unavailable (Employee.operational_status = suspended) is skipped.
    # Their existing assignments in already-approved plans are untouched.
    from src.core.enums import OperationalStatus
    worker_infos: list[WorkerInfo] = []
    WorkerModel = Nurse if service_type == ServiceType.nurse else Technician
    workers_q = (
        db.query(WorkerModel, Employee)
        .join(Employee, WorkerModel.employee_id == Employee.id)
        .filter(
            Employee.company_id == company_id,
            Employee.operational_status == OperationalStatus.active,
            Employee.deleted_at.is_(None),
        )
        .all()
    )
    for worker, emp in workers_q:
        skills = frozenset(
            s.value if hasattr(s, "value") else str(s) for s in (worker.skills or [])
        )
        worker_infos.append(WorkerInfo(
            id=worker.id, worker_type=service_type, skills=skills,
            shift_start=emp.shift_start, shift_end=emp.shift_end,
        ))

    # ---- vehicles -----------------------------------------------------------
    vehicles_q = db.query(Vehicle).filter(Vehicle.company_id == company_id).all()
    vehicle_infos: list[VehicleInfo] = []
    for v in vehicles_q:
        ftype = v.fuel_type.value if v.fuel_type else "petrol"
        vehicle_infos.append(VehicleInfo(
            id=v.id,
            vehicle_type=v.type.value if v.type else "car",
            seating_capacity=int(v.seating_capacity or 1),
            avg_speed_kmh=float(v.avg_speed_kmh or 40),
            fuel_type=ftype,
            fuel_average=float(v.fuel_average or 0),
            fuel_price=float(settings.FUEL_PRICES.get(ftype, 0.0)),
        ))

    # ---- drivers ------------------------------------------------------------
    drivers_q = db.query(Driver).filter(Driver.company_id == company_id).all()
    driver_infos: list[DriverInfo] = []
    for d in drivers_q:
        elig = frozenset(
            s.value if hasattr(s, "value") else str(s) for s in (d.skills or [])
        )
        driver_infos.append(DriverInfo(
            id=d.id, vehicle_id=d.vehicle_id, eligible_vehicle_types=elig,
        ))

    # ---- travel stack -------------------------------------------------------
    if provider is None:
        provider = OSMnxProvider(db)
    if active_hours is None:
        active_hours = _infer_active_hours(worker_infos)

    stack, distance = build_travel_stack(nodes, provider, dtype, active_hours)

    # only OSMnx-style providers expose per-leg road geometry for persistence
    geometry_source = provider if hasattr(provider, "leg_geometry") else None

    return ProblemData(
        company_id=company_id,
        planned_date=planned_date,
        service_type=service_type,
        day_type=dtype,
        nodes=nodes,
        depot_node_index=0,
        orders=order_infos,
        workers=worker_infos,
        drivers=driver_infos,
        vehicles=vehicle_infos,
        travel_time_sec=stack,
        distance_m=distance,
        active_hours=tuple(active_hours),
        geometry_source=geometry_source,
    )


def _infer_active_hours(workers: Sequence[WorkerInfo]) -> tuple[int, ...]:
    """
    Hours to build the matrix stack for: the span covered by worker shifts,
    falling back to a full working day (8-18) if no shifts are set.
    """
    starts = [w.shift_start.hour for w in workers if w.shift_start]
    ends = [w.shift_end.hour for w in workers if w.shift_end]
    if not starts or not ends:
        return tuple(range(8, 19))
    lo, hi = min(starts), max(ends)
    return tuple(range(lo, hi + 1))
