"""src/schemas/dashboard.py — today's ops-summary schema for the web dashboard."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class OrderStatusCounts(BaseModel):
    pending: int = 0
    assigned: int = 0
    in_transit: int = 0
    delivered: int = 0
    failed: int = 0


class PlanStatusCounts(BaseModel):
    draft: int = 0
    optimizing: int = 0
    ready: int = 0
    dispatched: int = 0
    completed: int = 0
    failed: int = 0


class DashboardToday(BaseModel):
    date: date
    orders_today: int
    order_status_counts: OrderStatusCounts
    completion_pct: float                  # delivered / total today
    plans_today: int
    plan_status_counts: PlanStatusCounts
    workers_total: int
    workers_available: int
    workers_unavailable: int
    drivers_total: int
    vehicles_total: int
