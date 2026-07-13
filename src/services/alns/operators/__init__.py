"""
src/services/alns/operators/

Destroy and repair operators for the ALNS loop. Each is a plain function with
the alns signature ``fn(state, rng) -> state`` and is registered via
ALNS.add_destroy_operator / add_repair_operator in solver.py.
"""

from src.services.alns.operators.destroy import (
    random_removal,
    worst_removal,
    shuttle_cost_removal,
    DESTROY_OPERATORS,
)
from src.services.alns.operators.repair import (
    greedy_insertion,
    regret2_insertion,
    shuttle_aware_greedy_insertion,
    REPAIR_OPERATORS,
)

__all__ = [
    "random_removal", "worst_removal", "shuttle_cost_removal", "DESTROY_OPERATORS",
    "greedy_insertion", "regret2_insertion", "shuttle_aware_greedy_insertion",
    "REPAIR_OPERATORS",
]
