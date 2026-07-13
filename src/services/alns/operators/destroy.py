"""
src/services/alns/operators/destroy.py

Destroy operators (plan Section 6). Each removes some orders from their worker
sequences back into state.unassigned, returning a NEW state (operators receive
a copy from the ALNS loop and mutate it freely).

alns signature: fn(state: RoutingState, rng: numpy.random.Generator) -> RoutingState

IMPORTANT (alns contract): alns does NOT defensively copy — it holds
curr = best = initial_solution as the same object. A destroy operator therefore
MUST copy the incoming state before mutating, or it corrupts curr/best/initial.
Each operator below calls state.copy() first. Repair operators receive the
destroyed COPY and may mutate it in place.
"""

from __future__ import annotations

import math

from src.services.alns.state import RoutingState


def _degree_of_destruction(state: RoutingState, rng) -> int:
    """
    Number of orders to remove: a fraction of currently-assigned orders,
    within the configured destroy_pct_range. At least 1 if anything is assigned.
    """
    from src.core.config import settings
    lo, hi = settings.ALNS_CONFIG.get("destroy_pct_range", [0.1, 0.3])
    assigned = [oid for seq in state.worker_routes.values() for oid in seq]
    if not assigned:
        return 0
    pct = rng.uniform(lo, hi)
    return max(1, min(len(assigned), math.ceil(len(assigned) * pct)))


def random_removal(state: RoutingState, rng) -> RoutingState:
    """Diversity anchor: unassign N random assigned orders."""
    state = state.copy()   # never mutate the incoming state (alns contract)
    n = _degree_of_destruction(state, rng)
    assigned = [oid for seq in state.worker_routes.values() for oid in seq]
    if not assigned:
        return state
    victims = rng.choice(assigned, size=n, replace=False)
    for oid in victims:
        state.unassign(int(oid))
    return state


def worst_removal(state: RoutingState, rng) -> RoutingState:
    """
    Remove the orders contributing the most cost — here, the orders with the
    highest per-order (tardiness + wait) in the derived timeline. Ties broken
    randomly to avoid getting stuck.
    """
    state = state.copy()   # never mutate the incoming state (alns contract)
    n = _degree_of_destruction(state, rng)
    if n == 0:
        return state
    sched = state.derive_driver_routes()

    scored: list[tuple[float, int]] = []
    for visits in sched.visits_by_worker.values():
        for v in visits:
            cost = v.tardiness_sec + v.wait_sec
            # small random jitter so equal-cost orders don't always pick the same
            scored.append((cost + rng.uniform(0, 1e-6), v.order_id))
    if not scored:
        return state
    scored.sort(reverse=True)
    for _cost, oid in scored[:n]:
        state.unassign(oid)
    return state


def shuttle_cost_removal(state: RoutingState, rng) -> RoutingState:
    """
    Custom, DARP-specific: remove the orders whose derived shuttle leg came out
    most expensive / barely-feasible (highest pickup delay). Directly targets
    whatever ExcessWaitCost / ShuttleInfeasibilityCost flagged.
    """
    state = state.copy()   # never mutate the incoming state (alns contract)
    n = _degree_of_destruction(state, rng)
    if n == 0:
        return state
    sched = state.derive_driver_routes()

    # map each delayed transport event back to the order it was delivering.
    # a leg's to_node identifies the order being reached.
    pd = state.problem_data
    node_to_order = {o.node_index: o.id for o in pd.orders}

    scored: list[tuple[float, int]] = []
    for leg in sched.legs:
        oid = node_to_order.get(leg.to_node)
        if oid is None:
            continue
        scored.append((leg.delay_sec + rng.uniform(0, 1e-6), oid))
    # also fold in fully-infeasible events (no driver) if any
    for ev, delay in sched.delayed_events:
        oid = node_to_order.get(ev.to_node)
        if oid is not None:
            scored.append((delay + rng.uniform(0, 1e-6), oid))

    if not scored:
        # nothing shuttle-expensive; fall back to random removal on our copy
        # (inline, not random_removal(), to avoid a redundant second copy)
        assigned = [oid for seq in state.worker_routes.values() for oid in seq]
        if assigned:
            for oid in rng.choice(assigned, size=n, replace=False):
                state.unassign(int(oid))
        return state

    scored.sort(reverse=True)
    seen = set()
    removed = 0
    for _cost, oid in scored:
        if oid in seen:
            continue
        seen.add(oid)
        state.unassign(oid)
        removed += 1
        if removed >= n:
            break
    return state


DESTROY_OPERATORS = [
    ("random_removal", random_removal),
    ("worst_removal", worst_removal),
    ("shuttle_cost_removal", shuttle_cost_removal),
]
