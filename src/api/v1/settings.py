"""
src/api/v1/settings.py

Console settings, including the demo-data tools.

The demo box needs refreshing regularly: seeded orders are dated relative to the
day the seed ran, and the route-plan picker only shows orders from today onward,
so a week-old dataset has nothing solvable in it. Previously that meant SSHing
into the VM and running a script — not something a salesperson can do mid-demo.

The reseed is DESTRUCTIVE and GLOBAL: it clears every tenant table for BOTH demo
companies, not just the caller's. Three guards, because an HTTP endpoint that
wipes a database deserves them:

  1. settings.DEMO_TOOLS_ENABLED — off unless a deployment opts in. A production
     box never exposes this, whatever a caller sends.
  2. an authenticated admin — role is checked, not just the token.
  3. an explicit confirm flag in the body, so a stray POST cannot fire it.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.v1.deps import get_current_user, CurrentUser
from src.core.config import settings as app_settings
from src.db.database import get_db
from src.exceptions.common import AppException, ValidationFailed
from src.schemas.settings import (
    DemoDataStatus,
    ReseedDemoDataRequest,
    ReseedDemoDataResponse,
)
from src.services import demo_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/settings", tags=["settings"])


class DemoToolsDisabled(AppException):
    def __init__(self):
        super().__init__(
            403, "demo_tools_disabled",
            "Demo data tools are disabled on this deployment.",
        )


class AdminRequired(AppException):
    def __init__(self):
        super().__init__(
            403, "admin_required",
            "Only an admin can reset demo data.",
        )


@router.get("/demo-data", response_model=DemoDataStatus)
def demo_data_status(current: CurrentUser = Depends(get_current_user)):
    """Whether the reseed button should be shown, and to whom."""
    return DemoDataStatus(
        enabled=app_settings.DEMO_TOOLS_ENABLED,
        is_admin=current.role == "admin",
    )


@router.post("/demo-data/reseed", response_model=ReseedDemoDataResponse)
def reseed_demo_data(
    body: ReseedDemoDataRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Wipe all tenant data and seed a fresh demo dataset dated from today.

    Clears orders, customers, workers, vehicles, depots, plans and assignments
    for BOTH demo companies. Company records and admin logins survive, so the
    caller stays logged in afterwards.
    """
    if not app_settings.DEMO_TOOLS_ENABLED:
        raise DemoToolsDisabled()
    if current.role != "admin":
        raise AdminRequired()
    if not body.confirm:
        raise ValidationFailed("Set confirm=true to reset demo data.")

    logger.warning(
        f"Demo data reseed triggered by user {current.username!r} "
        f"(id={current.user_id}, company={current.company_id})"
    )
    result = demo_data.reset_and_seed(db)

    return ReseedDemoDataResponse(
        removed_rows=result["removed_rows"],
        orders=result["orders"],
        customers=result["customers"],
        employees=result["employees"],
    )
