"""
src/services/alns/

ALNS route-optimization engine for the nurse/technician field-service
DARP-hybrid problem. All solver logic lives under this package:

    problem_data.py   -- DB/synthetic -> immutable in-memory ProblemData
    state.py          -- (later) RoutingState implementing alns.State
    cost.py           -- (later) modular CostComponent objective
    solver.py         -- (later) alns.ALNS loop wiring
    operators/        -- (later) destroy + repair operators

This pass ships problem_data.py only.
"""

from src.services.alns.problem_data import (
    ProblemData,
    TravelTimeProvider,
    HaversineProvider,
    OSMnxProvider,
    load_problem_data,
)

__all__ = [
    "ProblemData",
    "TravelTimeProvider",
    "HaversineProvider",
    "OSMnxProvider",
    "load_problem_data",
]
