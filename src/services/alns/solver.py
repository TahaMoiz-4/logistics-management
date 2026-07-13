"""
src/services/alns/solver.py

Wires ProblemData -> initial RoutingState -> alns.ALNS loop and runs it.

Loop config (plan Section 2, confirmed with user):
  * accept : SimulatedAnnealing (start/end temp + step from config/optimization_params)
  * select : SegmentedRouletteWheel (ρ1/ρ2/ρ3 adaptive weights)
  * stop   : MaxRuntime (seconds)

Repair-cost tradeoff (plan open-Q#8, delegated): greedy/regret use a cheap
worker-timeline proxy; a shuttle-aware variant uses the full driver-scheduling
pass per candidate. ``benchmark_repair_modes()`` measures both.

MEASURED (20 orders / 4 workers / 3 vehicles, seed 42, 8s each):
    proxy         : best=10,764  410 it/s  +17.7%
    shuttle_aware : best=10,378  265 it/s  +20.7%
=> shuttle_aware wins on solution quality (~3.6% better objective) despite ~35%
   fewer iterations — pricing real shuttle feasibility at insertion time beats
   the extra search throughput at this instance size. Default repair_mode is
   "proxy" for speed on large instances; callers wanting best quality on
   small/medium instances should pass repair_mode="shuttle_aware". Re-measure if
   instance size grows a lot (throughput gap may matter more).
"""

from __future__ import annotations

import time as _time
from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy.random as npr
from alns import ALNS
from alns.accept import SimulatedAnnealing
from alns.select import SegmentedRouletteWheel
from alns.stop import MaxRuntime

from src.core.config import settings
from src.services.alns.problem_data import ProblemData
from src.services.alns.state import RoutingState, empty_state
from src.services.alns.cost import cost_breakdown
from src.services.alns.operators.destroy import DESTROY_OPERATORS
from src.services.alns.operators.repair import (
    greedy_insertion, regret2_insertion, shuttle_aware_greedy_insertion,
)


@dataclass
class SolveResult:
    best: RoutingState
    initial_objective: float
    best_objective: float
    improvement_pct: float
    iterations: int
    runtime_sec: float
    breakdown: dict
    raw_result: object = None   # the raw alns.Result (statistics/trace for diagnostics)


def _merge_config(overrides: Optional[dict]) -> dict:
    """ALNS loop config = settings defaults, shallow-overridden per run."""
    cfg = dict(settings.ALNS_CONFIG)
    if overrides:
        cfg.update(overrides)
    return cfg


def build_initial_solution(pd: ProblemData, rng) -> RoutingState:
    """
    Greedy construction: start from empty and run cheap greedy insertion once.
    Gives ALNS a complete (if suboptimal) starting point to improve on.
    """
    state = empty_state(pd)
    return greedy_insertion(state, rng)


def solve(
    pd: ProblemData,
    config_overrides: Optional[dict] = None,
    repair_mode: str = "proxy",
    progress_cb=None,
) -> SolveResult:
    """
    Run the full ALNS optimization on a ProblemData instance.

    repair_mode:
      * "proxy"        -> greedy + regret2 (cheap worker-timeline cost). Default.
      * "shuttle_aware" -> greedy + regret2 + shuttle-aware greedy (full derive).

    progress_cb: optional callable(dict) invoked each time ALNS finds a new best
      solution — {iteration, best_objective, elapsed_sec}. Used by the SSE
      endpoint to stream live progress. Kept cheap; must not raise.
    """
    cfg = _merge_config(config_overrides)
    seed = int(cfg.get("seed", 42))
    rng = npr.default_rng(seed)

    initial = build_initial_solution(pd, rng)
    initial_obj = initial.objective()

    alns = ALNS(rng)
    for name, op in DESTROY_OPERATORS:
        alns.add_destroy_operator(op, name=name)

    repairs = [("greedy_insertion", greedy_insertion),
               ("regret2_insertion", regret2_insertion)]
    if repair_mode == "shuttle_aware":
        repairs.append(("shuttle_aware_greedy_insertion", shuttle_aware_greedy_insertion))
    for name, op in repairs:
        alns.add_repair_operator(op, name=name)

    select = SegmentedRouletteWheel(
        scores=[5, 2, 1, 0.5],   # ρ: new-best, better, accepted, rejected
        decay=0.8,
        seg_length=100,
        num_destroy=len(DESTROY_OPERATORS),
        num_repair=len(repairs),
    )
    accept = SimulatedAnnealing(
        start_temperature=float(cfg.get("sa_start_temp", 100.0)),
        end_temperature=float(cfg.get("sa_end_temp", 1.0)),
        step=float(cfg.get("sa_step", 0.9995)),
    )
    stop = MaxRuntime(float(cfg.get("max_runtime_sec", 60)))

    t0 = _time.perf_counter()

    # stream live progress for the SSE endpoint. We hook ALL four outcome
    # callbacks to (a) count iterations and (b) track the running best, then
    # emit a throttled snapshot every `emit_every` iterations — so the stream
    # shows continuous activity (current + best objective) even during long
    # stretches with no new global best. on_best also emits immediately.
    if progress_cb is not None:
        emit_every = int(cfg.get("progress_emit_every", 50))
        prog = {"iter": 0, "best": float("inf")}

        def _emit(candidate, is_best: bool):
            prog["iter"] += 1
            try:
                cur = float(candidate.objective())
            except Exception:
                return
            if is_best:
                prog["best"] = min(prog["best"], cur)
            if is_best or prog["iter"] % emit_every == 0:
                try:
                    progress_cb({
                        "event": "best" if is_best else "progress",
                        "iteration": prog["iter"],
                        "current_objective": round(cur, 3),
                        "best_objective": round(prog["best"], 3) if prog["best"] != float("inf") else None,
                        "elapsed_sec": round(_time.perf_counter() - t0, 3),
                    })
                except Exception:
                    pass  # progress reporting must never break the solve

        alns.on_best(lambda c, rnd, **k: _emit(c, True))
        alns.on_better(lambda c, rnd, **k: _emit(c, False))
        alns.on_accept(lambda c, rnd, **k: _emit(c, False))
        alns.on_reject(lambda c, rnd, **k: _emit(c, False))

    result = alns.iterate(initial, select, accept, stop)
    runtime = _time.perf_counter() - t0

    best = result.best_state
    best_obj = best.objective()
    improvement = (initial_obj - best_obj) / initial_obj * 100 if initial_obj else 0.0

    return SolveResult(
        best=best,
        initial_objective=initial_obj,
        best_objective=best_obj,
        improvement_pct=improvement,
        iterations=len(result.statistics.objectives),
        runtime_sec=runtime,
        breakdown=cost_breakdown(best),
        raw_result=result,
    )


def benchmark_repair_modes(pd: ProblemData, runtime_sec: float = 10.0) -> dict:
    """
    Measure proxy vs shuttle-aware repair on the same instance (plan Q#8).
    Returns a dict with each mode's best objective, iterations, and throughput.
    """
    out = {}
    for mode in ("proxy", "shuttle_aware"):
        res = solve(pd, config_overrides={"max_runtime_sec": runtime_sec}, repair_mode=mode)
        out[mode] = {
            "best_objective": round(res.best_objective, 2),
            "iterations": res.iterations,
            "iters_per_sec": round(res.iterations / res.runtime_sec, 1) if res.runtime_sec else 0,
            "improvement_pct": round(res.improvement_pct, 1),
        }
    return out
