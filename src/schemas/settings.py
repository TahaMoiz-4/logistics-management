"""src/schemas/settings.py — console settings + demo-data tooling."""

from __future__ import annotations
from pydantic import BaseModel


class DemoDataStatus(BaseModel):
    """Drives whether the console shows the reseed control at all."""
    enabled: bool      # settings.DEMO_TOOLS_ENABLED on this deployment
    is_admin: bool     # the caller's role allows running it


class ReseedDemoDataRequest(BaseModel):
    # Explicit opt-in so a stray POST cannot wipe the database.
    confirm: bool = False


class ReseedDemoDataResponse(BaseModel):
    removed_rows: int
    orders: int
    customers: int
    employees: int
