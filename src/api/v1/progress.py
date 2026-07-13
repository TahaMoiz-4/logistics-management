"""
src/api/v1/progress.py

In-process registry bridging a background solve (running in a worker thread via
FastAPI BackgroundTasks) to the SSE endpoint that streams its progress.

Single-process demo design: a dict of per-route-plan thread-safe queues. The
solve's progress_cb (called from the solver thread) pushes events; the SSE
endpoint (async) drains them. A sentinel marks completion.

Not multi-worker safe by design (would need Redis pub/sub) — fine for the demo,
per the chosen approach.
"""

from __future__ import annotations

import queue
import threading
from typing import Optional

# sentinel pushed to signal the solve is finished (success or failure)
DONE = object()

_registry: dict[int, "queue.Queue"] = {}
_lock = threading.Lock()


def create_channel(route_plan_id: int) -> "queue.Queue":
    """Register (or reset) a progress channel for a route plan."""
    q: queue.Queue = queue.Queue()
    with _lock:
        _registry[route_plan_id] = q
    return q


def get_channel(route_plan_id: int) -> Optional["queue.Queue"]:
    with _lock:
        return _registry.get(route_plan_id)


def publish(route_plan_id: int, event: dict) -> None:
    """Push a progress event (called from the solver thread). Non-blocking."""
    q = get_channel(route_plan_id)
    if q is not None:
        q.put(event)


def finish(route_plan_id: int, final: Optional[dict] = None) -> None:
    """Signal completion: push an optional final event then the DONE sentinel."""
    q = get_channel(route_plan_id)
    if q is not None:
        if final is not None:
            q.put(final)
        q.put(DONE)


def drop_channel(route_plan_id: int) -> None:
    with _lock:
        _registry.pop(route_plan_id, None)
