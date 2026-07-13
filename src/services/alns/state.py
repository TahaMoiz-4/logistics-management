"""
src/services/alns/state.py

The mutable solution representation for the ALNS search.

Design (plan Section 4 — worker-centric, driver-derived):
* ``RoutingState`` holds ONLY per-worker order sequences + the unassigned pool.
  Destroy/repair operators mutate these and nothing else — simple and fast.
* Driver-shuttle routing is DERIVED, not searched: ``derive_driver_routes()``
  is a deterministic scheduling pass that assigns the nearest feasible
  driver+vehicle to each transport event a worker's sequence implies. It never
  hard-fails — it always assigns *some* driver, however late, and reports the
  lateness so the cost function can price it (ExcessWaitCost /
  ShuttleInfeasibilityCost). This keeps the two layers from silently drifting.
* ``problem_data`` is an immutable shared reference — never copied per iteration.

All times are handled as "seconds since midnight of the planned date" (a float),
which keeps arithmetic trivial. Workers start their day at the depot.
"""

from __future__ import annotations

import copy as _copy
from dataclasses import dataclass, field
from datetime import time
from typing import Optional

from alns import State

from src.services.alns.problem_data import ProblemData, WorkerInfo


# ---------------------------------------------------------------------------
# Derived-schedule value types (plain data)
# ---------------------------------------------------------------------------

@dataclass
class ServiceVisit:
    """One order served by a worker, with computed timing (seconds-since-midnight)."""
    worker_id: int
    order_id: int
    seq: int
    node_index: int
    arrival_sec: float          # when the worker reaches the order location
    service_start_sec: float    # max(arrival, timewindow_start)
    service_end_sec: float      # service_start + service_duration
    wait_sec: float             # idle wait before service could begin
    tardiness_sec: float        # lateness vs timewindow_end (0 if on time)


@dataclass
class TransportEvent:
    """
    A leg where a worker must be moved from `from_node` to `to_node`, arriving
    by `needed_by_sec`. Produced by the derive pass; consumed by the driver
    scheduler and the shuttle cost components.
    """
    worker_id: int
    from_node: int
    to_node: int
    earliest_sec: float          # worker available to depart from_node
    needed_by_sec: float         # ideal arrival at to_node (service window)


@dataclass
class DerivedDriverLeg:
    """One assigned shuttle leg in the derived driver schedule."""
    driver_id: int
    vehicle_id: int
    from_node: int
    to_node: int                 # representative destination (pooled riders share a zone)
    depart_sec: float
    arrive_sec: float
    rider_worker_ids: list[int]
    delay_sec: float             # arrival delay vs the event's needed_by_sec
    # per-rider actual destination node (pooled riders may sit in the same H3
    # zone but at slightly different nodes) -> {worker_id: to_node}. Lets
    # persistence link each rider's service stop to this leg precisely.
    rider_to_nodes: dict = field(default_factory=dict)


@dataclass
class DerivedSchedule:
    """Full output of derive_driver_routes(): legs + the timing/infeasibility signals."""
    legs: list[DerivedDriverLeg]
    visits_by_worker: dict[int, list[ServiceVisit]]
    # transport events that arrived later than needed, with the delay in seconds
    delayed_events: list[tuple[TransportEvent, float]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _time_to_sec(t: Optional[time], default_sec: float) -> float:
    if t is None:
        return default_sec
    return t.hour * 3600 + t.minute * 60 + t.second


def _sec_to_hour(sec: float) -> int:
    """Departure hour bucket for the per-hour travel matrix (clamped 0..23)."""
    h = int(sec // 3600)
    return max(0, min(23, h))


# ---------------------------------------------------------------------------
# RoutingState
# ---------------------------------------------------------------------------

@dataclass
class RoutingState(State):
    """
    alns.State implementation. Primary structure: per-worker order sequences.

    worker_routes : {worker_id -> [order_id, ...]}  (order matters = service seq)
    unassigned    : [order_id, ...]                 (orders with no worker yet)
    problem_data  : immutable shared reference
    """
    worker_routes: dict[int, list[int]]
    unassigned: list[int]
    problem_data: ProblemData

    # penalty/threshold config resolved for this solve (defaults from settings,
    # possibly overridden per-run). Injected so cost + scheduler agree on values.
    penalties: dict = field(default_factory=dict)
    excess_wait_threshold_sec: float = 15 * 60
    shuttle_infeasible_after_sec: float = 45 * 60

    # lazily-computed cache of the derived driver schedule; invalidated on copy
    # and whenever worker_routes is mutated (callers use invalidate()).
    _derived: Optional[DerivedSchedule] = field(default=None, repr=False, compare=False)

    # ---- alns.State interface ----------------------------------------------

    def objective(self) -> float:
        # imported here to avoid a circular import (cost imports state types)
        from src.services.alns.cost import compute_cost
        return compute_cost(self)

    def copy(self) -> "RoutingState":
        clone = RoutingState(
            worker_routes={w: list(seq) for w, seq in self.worker_routes.items()},
            unassigned=list(self.unassigned),
            problem_data=self.problem_data,          # shared, not copied
            penalties=self.penalties,                # read-only config, shared
            excess_wait_threshold_sec=self.excess_wait_threshold_sec,
            shuttle_infeasible_after_sec=self.shuttle_infeasible_after_sec,
        )
        # derived cache intentionally NOT copied — clone will likely be mutated
        # before objective() is next called, so recompute lazily.
        return clone

    # ---- mutation bookkeeping ----------------------------------------------

    def invalidate(self) -> None:
        """Drop the derived-schedule cache. Call after mutating worker_routes."""
        self._derived = None

    def assign(self, worker_id: int, order_id: int, position: Optional[int] = None) -> None:
        seq = self.worker_routes.setdefault(worker_id, [])
        if position is None:
            seq.append(order_id)
        else:
            seq.insert(position, order_id)
        if order_id in self.unassigned:
            self.unassigned.remove(order_id)
        self.invalidate()

    def unassign(self, order_id: int) -> None:
        for seq in self.worker_routes.values():
            if order_id in seq:
                seq.remove(order_id)
                break
        if order_id not in self.unassigned:
            self.unassigned.append(order_id)
        self.invalidate()

    # ---- worker timeline ----------------------------------------------------

    def _compute_visits(self, worker: WorkerInfo, seq: list[int]) -> list[ServiceVisit]:
        """
        Walk a worker's order sequence, computing arrival/service/departure times.
        The worker starts at the depot at shift_start and travels order-to-order.
        Travel time is taken from the per-hour matrix keyed on departure hour.
        """
        pd = self.problem_data
        visits: list[ServiceVisit] = []
        # start of day: shift_start (fallback: first active hour)
        default_start = pd.active_hours[0] * 3600 if pd.active_hours else 8 * 3600
        clock = _time_to_sec(worker.shift_start, default_start)
        prev_node = pd.depot_node_index

        for i, order_id in enumerate(seq):
            o = pd.order_by_id[order_id]
            hour = _sec_to_hour(clock)
            travel = pd.travel_time(prev_node, o.node_index, hour)
            arrival = clock + travel

            tw_start = self._tw_sec(o.timewindow_start)
            service_start = max(arrival, tw_start) if tw_start is not None else arrival
            wait = max(0.0, service_start - arrival)
            service_end = service_start + o.service_duration_sec

            tw_end = self._tw_sec(o.timewindow_end)
            tardiness = max(0.0, service_end - tw_end) if tw_end is not None else 0.0

            visits.append(ServiceVisit(
                worker_id=worker.id, order_id=order_id, seq=i,
                node_index=o.node_index, arrival_sec=arrival,
                service_start_sec=service_start, service_end_sec=service_end,
                wait_sec=wait, tardiness_sec=tardiness,
            ))
            clock = service_end
            prev_node = o.node_index
        return visits

    def _tw_sec(self, dt) -> Optional[float]:
        """Time window datetime -> seconds since midnight of its own date."""
        if dt is None:
            return None
        return dt.hour * 3600 + dt.minute * 60 + dt.second

    # ---- driver-shuttle derivation -----------------------------------------

    def derive_driver_routes(self) -> DerivedSchedule:
        """
        Deterministic scheduling pass (plan Section 4). For every transport
        event a worker's sequence implies (depot->first order, and order->order),
        greedily assign the nearest feasible driver+vehicle by earliest possible
        arrival, respecting seating_capacity and driver->vehicle eligibility.

        Never hard-fails: always assigns the best-available driver, records the
        arrival delay vs. needed_by. Delays are surfaced in `delayed_events` for
        the cost function to price (wait / infeasibility). Cached until invalidate().
        """
        if self._derived is not None:
            return self._derived

        pd = self.problem_data

        # 1. compute each worker's service timeline + the transport events they need
        visits_by_worker: dict[int, list[ServiceVisit]] = {}
        events: list[TransportEvent] = []
        for worker_id, seq in self.worker_routes.items():
            if not seq:
                continue
            worker = pd.worker_by_id[worker_id]
            visits = self._compute_visits(worker, seq)
            visits_by_worker[worker_id] = visits

            prev_node = pd.depot_node_index
            prev_ready = _time_to_sec(
                worker.shift_start,
                pd.active_hours[0] * 3600 if pd.active_hours else 8 * 3600,
            )
            for v in visits:
                events.append(TransportEvent(
                    worker_id=worker_id, from_node=prev_node, to_node=v.node_index,
                    earliest_sec=prev_ready, needed_by_sec=v.service_start_sec,
                ))
                prev_node = v.node_index
                prev_ready = v.service_end_sec

        # 2. group poolable events, then schedule each group as ONE driver leg.
        driver_state = {
            d.id: {"free_sec": 0.0, "node": pd.depot_node_index, "vehicle_id": d.vehicle_id}
            for d in pd.drivers
        }
        legs: list[DerivedDriverLeg] = []
        delayed: list[tuple[TransportEvent, float]] = []

        # split any pooled group larger than the biggest available vehicle into
        # capacity-sized chunks (staggered pickups) so overflow doesn't fail.
        max_seats = max((v.seating_capacity or 1 for v in pd.vehicles), default=1)
        for group in self._split_to_capacity(self._pool_events(events), max_seats):
            best = self._pick_driver(group[0], driver_state, riders_needed=len(group))
            if best is None:
                # no driver with capacity (or none at all) — treat every rider as
                # fully delayed so ShuttleInfeasibilityCost fires loudly.
                for ev in group:
                    delayed.append((ev, self.shuttle_infeasible_after_sec))
                continue

            driver_id, arrive_sec, depart_sec, vehicle_id = best
            rep = group[0]   # all riders share from-node + destination zone + time bucket
            legs.append(DerivedDriverLeg(
                driver_id=driver_id, vehicle_id=vehicle_id,
                from_node=rep.from_node, to_node=rep.to_node,
                depart_sec=depart_sec, arrive_sec=arrive_sec,
                rider_worker_ids=[ev.worker_id for ev in group], delay_sec=0.0,
                rider_to_nodes={ev.worker_id: ev.to_node for ev in group},
            ))
            driver_state[driver_id]["free_sec"] = arrive_sec
            driver_state[driver_id]["node"] = rep.to_node
            # delay is priced per rider against THEIR own needed_by
            leg_delay = 0.0
            for ev in group:
                d = max(0.0, arrive_sec - ev.needed_by_sec)
                leg_delay = max(leg_delay, d)
                if d > 0:
                    delayed.append((ev, d))
            legs[-1].delay_sec = leg_delay

        self._derived = DerivedSchedule(
            legs=legs, visits_by_worker=visits_by_worker, delayed_events=delayed,
        )
        return self._derived

    def _pool_events(self, events: list[TransportEvent]) -> list[list[TransportEvent]]:
        """
        Group transport events into poolable clusters (DARP ride-sharing).

        Two events pool together iff their DESTINATION is in the same H3 zone
        (from ProblemData node zone_h3) AND their ideal arrival times fall in the
        same POOL_WINDOW_MIN bucket. Uses a hash bucket keyed on
        (dest_zone_h3, time_bucket) — a single linear pass, no pairwise compare.

        Pooling can be disabled (POOL_ENABLED=False) — then every event is its
        own singleton group, i.e. the original one-rider-per-leg behaviour.

        Capacity is NOT enforced here; it's enforced at driver assignment, where
        an oversized group that no vehicle can seat falls back to the shuttle
        infeasibility signal (staggering emerges from ALNS reshuffling worker
        sequences, keeping this pass simple and fast).
        """
        from src.core.config import settings
        if not settings.POOL_ENABLED:
            return [[ev] for ev in sorted(events, key=lambda e: e.earliest_sec)]

        pd = self.problem_data
        window_sec = settings.POOL_WINDOW_MIN * 60
        buckets: dict[tuple, list[TransportEvent]] = {}
        for ev in sorted(events, key=lambda e: e.earliest_sec):
            dest_zone = pd.nodes[ev.to_node].zone_h3 or f"node:{ev.to_node}"
            tbucket = int(ev.needed_by_sec // window_sec) if window_sec else 0
            buckets.setdefault((dest_zone, tbucket), []).append(ev)
        # deterministic order: earliest group first
        return [g for _k, g in sorted(buckets.items(), key=lambda kv: kv[1][0].earliest_sec)]

    @staticmethod
    def _split_to_capacity(groups: list[list[TransportEvent]], max_seats: int):
        """
        Split any pooled group larger than max_seats into capacity-sized chunks,
        so a same-zone/time cluster bigger than the largest vehicle is served by
        several staggered legs rather than declared infeasible. Preserves order.
        """
        cap = max(1, int(max_seats))
        out: list[list[TransportEvent]] = []
        for g in groups:
            if len(g) <= cap:
                out.append(g)
            else:
                for i in range(0, len(g), cap):
                    out.append(g[i:i + cap])
        return out

    def _pick_driver(self, ev: TransportEvent, driver_state: dict, riders_needed: int = 1):
        """
        Choose the driver who can deliver this transport event earliest, whose
        vehicle can seat `riders_needed` riders. A driver deadheads from their
        current node to from_node, then carries the riders to to_node. Returns
        (driver_id, arrive_sec, depart_sec, vehicle_id) or None if no eligible
        driver has enough capacity.
        """
        pd = self.problem_data
        best = None
        for driver_id, st in driver_state.items():
            vehicle_id = st["vehicle_id"]
            if vehicle_id is None:
                continue
            if not pd.driver_can_drive(driver_id, vehicle_id):
                continue
            # capacity: the vehicle must seat everyone in the pooled group
            vinfo = pd.vehicle_by_id.get(vehicle_id)
            capacity = vinfo.seating_capacity if vinfo else 1
            if capacity < riders_needed:
                continue

            # deadhead: driver's current node -> pickup (from_node)
            ready = max(st["free_sec"], ev.earliest_sec)
            deadhead_hour = _sec_to_hour(ready)
            deadhead = pd.travel_time(st["node"], ev.from_node, deadhead_hour)
            depart_sec = ready + deadhead
            # carry: from_node -> to_node
            carry_hour = _sec_to_hour(depart_sec)
            carry = pd.travel_time(ev.from_node, ev.to_node, carry_hour)
            arrive_sec = depart_sec + carry

            if best is None or arrive_sec < best[1]:
                best = (driver_id, arrive_sec, depart_sec, vehicle_id)
        return best


# ---------------------------------------------------------------------------
# Initial-state construction
# ---------------------------------------------------------------------------

def empty_state(pd: ProblemData) -> RoutingState:
    """A state with every order unassigned and every worker idle."""
    from src.core.config import settings
    return RoutingState(
        worker_routes={w.id: [] for w in pd.workers},
        unassigned=[o.id for o in pd.orders],
        problem_data=pd,
        penalties=dict(settings.ALNS_PENALTIES),
        excess_wait_threshold_sec=settings.EXCESS_WAIT_THRESHOLD_MIN * 60,
        shuttle_infeasible_after_sec=settings.SHUTTLE_INFEASIBLE_AFTER_MIN * 60,
    )
