"""
src/api/v1/dashboard.py

Today's operations summary for the web dashboard landing page (polling).
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.db.database import get_db
from src.db.models import Order, RoutePlan, Employee, Driver, Vehicle, Company
from src.core.enums import OrderStatus, PlanStatus, ServiceType, OperationalStatus
from src.api.v1.deps import get_current_user, CurrentUser
from src.schemas.dashboard import (
    DashboardToday, OrderStatusCounts, PlanStatusCounts,
)

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/today", response_model=DashboardToday)
def dashboard_today(
    on_date: date | None = Query(None, alias="date", description="defaults to today"),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company_id = current.company_id
    day = on_date or date.today()

    # ── orders on this service_date, grouped by status ────────────────────────
    order_rows = (
        db.query(Order.status, func.count(Order.id))
        .filter(Order.company_id == company_id, Order.service_date == day,
                Order.deleted_at.is_(None))
        .group_by(Order.status)
        .all()
    )
    oc = OrderStatusCounts()
    total_orders = 0
    for status, cnt in order_rows:
        total_orders += cnt
        if status is not None:
            setattr(oc, status.value, cnt)
    completion_pct = round((oc.delivered / total_orders * 100), 1) if total_orders else 0.0

    # ── plans planned for this date, grouped by status ────────────────────────
    plan_rows = (
        db.query(RoutePlan.status, func.count(RoutePlan.id))
        .filter(RoutePlan.company_id == company_id, RoutePlan.planned_date == day,
                RoutePlan.deleted_at.is_(None))
        .group_by(RoutePlan.status)
        .all()
    )
    pc = PlanStatusCounts()
    total_plans = 0
    for status, cnt in plan_rows:
        total_plans += cnt
        if status is not None:
            setattr(pc, status.value, cnt)

    # ── workforce ─────────────────────────────────────────────────────────────
    emp_rows = (
        db.query(Employee.operational_status, func.count(Employee.id))
        .filter(Employee.company_id == company_id, Employee.deleted_at.is_(None))
        .group_by(Employee.operational_status)
        .all()
    )
    workers_total = sum(c for _, c in emp_rows)
    workers_available = sum(c for s, c in emp_rows if s == OperationalStatus.active)

    drivers_total = (
        db.query(func.count(Driver.id))
        .filter(Driver.company_id == company_id, Driver.deleted_at.is_(None)).scalar()
    )
    vehicles_total = (
        db.query(func.count(Vehicle.id))
        .filter(Vehicle.company_id == company_id, Vehicle.deleted_at.is_(None)).scalar()
    )

    return DashboardToday(
        date=day, orders_today=total_orders, order_status_counts=oc,
        completion_pct=completion_pct, plans_today=total_plans, plan_status_counts=pc,
        workers_total=workers_total, workers_available=workers_available,
        workers_unavailable=workers_total - workers_available,
        drivers_total=drivers_total or 0, vehicles_total=vehicles_total or 0,
    )
