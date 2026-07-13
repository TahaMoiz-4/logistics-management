"""
src/services/alns/operators/repair.py

Repair operators (plan Section 6). Each reinserts every order in
state.unassigned into some (worker, position), hard-filtered by skill.

Two cost models for evaluating a candidate insertion (plan open-Q#8, delegated
to empirical judgment):
  * CHEAP PROXY (default): marginal worker-timeline cost — the extra travel +
    tardiness + wait the insertion adds to that worker's sequence, WITHOUT
    running the full driver-scheduling pass per candidate. Fast.
  * SHUTTLE-AWARE: evaluates the true objective delta via
    state.derive_driver_routes() per candidate. Accurate, slower.

greedy_insertion / regret2_insertion use the cheap proxy;
shuttle_aware_greedy_insertion uses the full derive. solver.py measures both.

alns signature: fn(state: RoutingState, rng) -> RoutingState
"""

from __future__ import annotations

from typing import Optional

from src.services.alns.state import RoutingState, _sec_to_hour, _time_to_sec


# ---------------------------------------------------------------------------
# Cheap proxy: marginal worker-timeline insertion cost
# ---------------------------------------------------------------------------

def _proxy_insertion_cost(
    state: RoutingState, worker_id: int, order_id: int, position: int
) -> float:
    """
    Approximate marginal cost of inserting order_id into worker's sequence at
    `position`, using only worker-timeline terms (no driver schedule). Lower is
    better. Returns the delta in (travel + tardiness*rate + wait*rate).
    """
    pd = state.problem_data
    worker = pd.worker_by_id[worker_id]
    tard_rate = state.penalties.get("tardiness_per_min", 0.0)
    wait_rate = state.penalties.get("excess_wait_per_min", 0.0)
    threshold = state.excess_wait_threshold_sec

    def timeline_cost(seq: list[int]) -> float:
        visits = state._compute_visits(worker, seq)
        # travel proxy = sum of leg travel times reconstructed from arrivals
        total = 0.0
        for v in visits:
            total += (v.tardiness_sec / 60.0) * tard_rate
            excess = v.wait_sec - threshold
            if excess > 0:
                total += (excess / 60.0) * wait_rate
        # add end-of-day time as a light travel proxy (later finish = more travel)
        if visits:
            total += visits[-1].service_end_sec / 3600.0  # hours, small weight
        return total

    base_seq = state.worker_routes.get(worker_id, [])
    new_seq = list(base_seq)
    new_seq.insert(position, order_id)
    return timeline_cost(new_seq) - timeline_cost(base_seq)


def _best_position_proxy(
    state: RoutingState, worker_id: int, order_id: int
) -> tuple[float, int]:
    """Cheapest insertion position for order in this worker (proxy cost)."""
    seq = state.worker_routes.get(worker_id, [])
    best_cost, best_pos = float("inf"), 0
    for pos in range(len(seq) + 1):
        c = _proxy_insertion_cost(state, worker_id, order_id, pos)
        if c < best_cost:
            best_cost, best_pos = c, pos
    return best_cost, best_pos


def _feasible_workers(state: RoutingState, order_id: int) -> list[int]:
    """Workers who hold all the order's required skills (hard filter)."""
    pd = state.problem_data
    return [w.id for w in pd.workers if pd.worker_can_serve(w.id, order_id)]


# ---------------------------------------------------------------------------
# Greedy insertion (cheap proxy)
# ---------------------------------------------------------------------------

def greedy_insertion(state: RoutingState, rng) -> RoutingState:
    """
    For each unassigned order (random order), insert at its globally cheapest
    feasible (worker, position) by proxy cost. Skill-hard-filtered. Orders with
    no feasible worker stay unassigned (UnservedOrderCost prices them).
    """
    orders = list(state.unassigned)
    rng.shuffle(orders)
    for order_id in orders:
        workers = _feasible_workers(state, order_id)
        if not workers:
            continue
        best = None  # (cost, worker_id, pos)
        for w in workers:
            c, pos = _best_position_proxy(state, w, order_id)
            if best is None or c < best[0]:
                best = (c, w, pos)
        _, w, pos = best
        state.assign(w, order_id, position=pos)
    return state


# ---------------------------------------------------------------------------
# Regret-2 insertion (cheap proxy)
# ---------------------------------------------------------------------------

def regret2_insertion(state: RoutingState, rng) -> RoutingState:
    """
    Insert orders in order of regret: the gap between the best and 2nd-best
    feasible worker's insertion cost. Orders with few feasible workers (high
    regret) get placed first, before their options get consumed.
    """
    remaining = list(state.unassigned)
    while remaining:
        best_choice = None  # (regret, cost, worker_id, pos, order_id)
        for order_id in remaining:
            workers = _feasible_workers(state, order_id)
            if not workers:
                continue
            # cheapest position per worker
            per_worker = sorted(
                (_best_position_proxy(state, w, order_id)[0], w, order_id)
                for w in workers
            )
            best_cost, best_w, _ = per_worker[0]
            second_cost = per_worker[1][0] if len(per_worker) > 1 else best_cost + 1e6
            regret = second_cost - best_cost
            _, best_pos = _best_position_proxy(state, best_w, order_id)
            cand = (regret, best_cost, best_w, best_pos, order_id)
            # maximize regret; tie-break on lower best_cost
            if best_choice is None or (cand[0], -cand[1]) > (best_choice[0], -best_choice[1]):
                best_choice = cand

        if best_choice is None:
            break  # nothing left is feasible
        _regret, _cost, w, pos, order_id = best_choice
        state.assign(w, order_id, position=pos)
        remaining.remove(order_id)

    return state


# ---------------------------------------------------------------------------
# Shuttle-aware greedy insertion (full derive per candidate)
# ---------------------------------------------------------------------------

def shuttle_aware_greedy_insertion(state: RoutingState, rng) -> RoutingState:
    """
    Same greedy shape, but each candidate is scored by the TRUE objective delta
    (state.objective() after a trial insert), which runs the full driver
    scheduling pass — so insertion cost reflects real shuttle feasibility, not
    just the worker timeline. Accurate, slower. Used to benchmark vs the proxy.
    """
    orders = list(state.unassigned)
    rng.shuffle(orders)
    for order_id in orders:
        workers = _feasible_workers(state, order_id)
        if not workers:
            continue
        best = None  # (obj, worker_id, pos)
        for w in workers:
            seq_len = len(state.worker_routes.get(w, []))
            for pos in range(seq_len + 1):
                state.assign(w, order_id, position=pos)
                obj = state.objective()
                state.unassign(order_id)   # revert trial
                if best is None or obj < best[0]:
                    best = (obj, w, pos)
        _, w, pos = best
        state.assign(w, order_id, position=pos)
    return state


DESTROY_HINT = "see destroy.py"

REPAIR_OPERATORS = [
    ("greedy_insertion", greedy_insertion),
    ("regret2_insertion", regret2_insertion),
    ("shuttle_aware_greedy_insertion", shuttle_aware_greedy_insertion),
]
