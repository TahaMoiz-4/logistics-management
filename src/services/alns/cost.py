"""
src/services/alns/cost.py

Modular objective function (plan Section 5). Every constraint/cost term is a
CostComponent; the objective is their sum. Adding a new constraint later means
writing one subclass and appending it to COST_COMPONENTS — compute_cost never
changes.

All components read penalty weights from ``state.penalties`` (resolved from
config defaults, possibly overridden per-run) so tuning is data, not code.
Travel/fuel/wait/infeasibility terms read the derived driver schedule via
``state.derive_driver_routes()`` (cached).
"""

from __future__ import annotations

from src.services.alns.state import RoutingState


class CostComponent:
    """Base class — every constraint/cost term implements evaluate()."""
    name: str = "cost"

    def evaluate(self, state: RoutingState) -> float:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Driver-shuttle terms (read the derived schedule)
# ---------------------------------------------------------------------------

class TravelTimeCost(CostComponent):
    """Total driver travel time across all derived shuttle legs (seconds)."""
    name = "travel_time"

    def evaluate(self, state: RoutingState) -> float:
        sched = state.derive_driver_routes()
        return sum(leg.arrive_sec - leg.depart_sec for leg in sched.legs)


class FuelCost(CostComponent):
    """
    Fuel cost over derived shuttle legs: distance_km * fuel_average * price.
    Distance is traffic-independent (ProblemData.distance), price/consumption
    come from the leg's vehicle.
    """
    name = "fuel"

    def evaluate(self, state: RoutingState) -> float:
        pd = state.problem_data
        total = 0.0
        for leg in sched_legs(state):
            v = pd.vehicle_by_id.get(leg.vehicle_id)
            if v is None:
                continue
            dist_km = pd.distance(leg.from_node, leg.to_node) / 1000.0
            total += dist_km * v.fuel_average * v.fuel_price
        return total


# ---------------------------------------------------------------------------
# Worker-timeline terms
# ---------------------------------------------------------------------------

class TardinessCost(CostComponent):
    """Per-order lateness beyond its time window, per minute."""
    name = "tardiness"

    def evaluate(self, state: RoutingState) -> float:
        rate = state.penalties.get("tardiness_per_min", 0.0)
        if rate == 0.0:
            return 0.0
        sched = state.derive_driver_routes()
        total_min = 0.0
        for visits in sched.visits_by_worker.values():
            for v in visits:
                total_min += v.tardiness_sec / 60.0
        return total_min * rate


class OvertimeCost(CostComponent):
    """Per-worker shift overrun (last service_end beyond shift_end), per minute."""
    name = "overtime"

    def evaluate(self, state: RoutingState) -> float:
        rate = state.penalties.get("overtime_per_min", 0.0)
        if rate == 0.0:
            return 0.0
        pd = state.problem_data
        sched = state.derive_driver_routes()
        total_min = 0.0
        for worker_id, visits in sched.visits_by_worker.items():
            if not visits:
                continue
            worker = pd.worker_by_id[worker_id]
            if worker.shift_end is None:
                continue
            shift_end_sec = worker.shift_end.hour * 3600 + worker.shift_end.minute * 60
            overrun = visits[-1].service_end_sec - shift_end_sec
            if overrun > 0:
                total_min += overrun / 60.0
        return total_min * rate


class SkillViolationCost(CostComponent):
    """
    Safety net: a worker assigned an order they lack the skill for. Should be
    near-zero because insertion is skill-hard-filtered, but priced so any leak
    is visible and steers the search away.
    """
    name = "skill_violation"

    def evaluate(self, state: RoutingState) -> float:
        pen = state.penalties.get("skill_violation", 0.0)
        if pen == 0.0:
            return 0.0
        pd = state.problem_data
        violations = 0
        for worker_id, seq in state.worker_routes.items():
            for order_id in seq:
                if not pd.worker_can_serve(worker_id, order_id):
                    violations += 1
        return violations * pen


class UnservedOrderCost(CostComponent):
    """Per order left in the unassigned pool."""
    name = "unserved"

    def evaluate(self, state: RoutingState) -> float:
        pen = state.penalties.get("unserved_order", 0.0)
        return len(state.unassigned) * pen


class ExcessWaitCost(CostComponent):
    """
    Worker idle wait (before service) and shuttle pickup delay beyond the free
    threshold, per minute. Reads both worker-timeline wait and derived-leg delay.
    """
    name = "excess_wait"

    def evaluate(self, state: RoutingState) -> float:
        rate = state.penalties.get("excess_wait_per_min", 0.0)
        if rate == 0.0:
            return 0.0
        threshold = state.excess_wait_threshold_sec
        sched = state.derive_driver_routes()

        total_min = 0.0
        # worker idle wait before a service could begin
        for visits in sched.visits_by_worker.values():
            for v in visits:
                excess = v.wait_sec - threshold
                if excess > 0:
                    total_min += excess / 60.0
        # shuttle pickup/dropoff delay beyond threshold
        for _ev, delay_sec in sched.delayed_events:
            excess = delay_sec - threshold
            if excess > 0:
                total_min += excess / 60.0
        return total_min * rate


class ShuttleInfeasibilityCost(CostComponent):
    """
    Flat penalty per transport event the scheduler couldn't feasibly deliver
    within shuttle_infeasible_after_sec. This is what keeps the worker-centric
    state honest about whether its sequences are actually deliverable by real
    drivers (plan Section 4). Same mechanism as UnservedOrderCost: a real cost
    signal, not a silent log line.
    """
    name = "shuttle_infeasible"

    def evaluate(self, state: RoutingState) -> float:
        pen = state.penalties.get("shuttle_infeasible", 0.0)
        if pen == 0.0:
            return 0.0
        cutoff = state.shuttle_infeasible_after_sec
        sched = state.derive_driver_routes()
        infeasible = sum(1 for _ev, delay in sched.delayed_events if delay >= cutoff)
        return infeasible * pen


# ---------------------------------------------------------------------------
# Registry + entrypoint
# ---------------------------------------------------------------------------

COST_COMPONENTS: list[CostComponent] = [
    TravelTimeCost(),
    FuelCost(),
    TardinessCost(),
    OvertimeCost(),
    SkillViolationCost(),
    UnservedOrderCost(),
    ExcessWaitCost(),
    ShuttleInfeasibilityCost(),
]


def sched_legs(state: RoutingState):
    """Convenience accessor for the derived legs (keeps FuelCost readable)."""
    return state.derive_driver_routes().legs


def compute_cost(state: RoutingState) -> float:
    """Objective f(s) = sum of all cost components. Lower is better."""
    return sum(c.evaluate(state) for c in COST_COMPONENTS)


def cost_breakdown(state: RoutingState) -> dict[str, float]:
    """Per-component breakdown — for debugging, tuning, and test assertions."""
    return {c.name: c.evaluate(state) for c in COST_COMPONENTS}
