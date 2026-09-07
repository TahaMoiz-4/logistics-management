"""
src/services/demo_data.py

Reset + reseed the demo dataset from the API, so a salesperson can refresh a
stale demo from the console instead of SSHing into the VM.

This wraps the same logic as the CLI scripts:
    src/utils/scripts/reset_tenant_data.py
    src/utils/scripts/seed_demo_dataset.py

but as a callable function rather than a __main__ that prints and reads argv.
The scripts stay the canonical entry point for operators with a shell; this is
the same work, callable from a request.

WHY THIS EXISTS: seeded orders are dated relative to the day the seed runs, and
the route-plan picker only lists orders from today onward. A dataset seeded last
week therefore has nothing solvable in it, and the demo looks broken.

SCOPE WARNING: the reset is GLOBAL, not per-company — it clears every tenant
table (both demo companies), exactly as the CLI script does. That is correct for
a demo box and wrong for anything holding real customer data, which is why the
endpoint calling this is gated on settings.DEMO_TOOLS_ENABLED.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def reset_and_seed(db: Session) -> dict:
    """
    Clear all tenant data, then seed a fresh demo dataset dated from today.

    Runs as ONE transaction: if seeding fails, the clear rolls back too, so a
    half-wiped database is not a possible outcome.

    Returns a summary of what was removed and what now exists.
    """
    from src.utils.scripts.reset_tenant_data import DELETE_ORDER
    from src.utils.scripts.seed_demo_dataset import _seed_company
    from src.core.enums import ServiceType

    logger.info("Demo data: reset + reseed requested")

    removed: dict[str, int] = {}
    try:
        # companies survive the reset but reference location rows we are about
        # to clear, so drop that FK first.
        db.execute(text("UPDATE companies SET head_office_location_id = NULL"))

        # Children before parents — every FK here is a plain reference with no
        # ON DELETE CASCADE, so a wrong order raises a FK violation.
        for table in DELETE_ORDER:
            removed[table] = db.execute(text(f"DELETE FROM {table}")).rowcount

        # Restart identity sequences so the reseed produces predictable ids
        # (employees from 1, giving worker1, worker2, ... logins).
        for table in DELETE_ORDER:
            db.execute(text(f"ALTER SEQUENCE IF EXISTS {table}_id_seq RESTART WITH 1"))

        # Seed both demo companies. _seed_company prints progress; harmless here
        # (it lands in the server log) and keeps this in step with the script.
        _seed_company(db, 1, "Aga Khan Home Care", ServiceType.nurse, "admin1")
        _seed_company(db, 2, "SysTech Field Services", ServiceType.technician, "admin2")

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Demo data: reset + reseed FAILED, rolled back")
        raise

    orders = db.execute(text("SELECT COUNT(*) FROM orders")).scalar_one()
    customers = db.execute(text("SELECT COUNT(*) FROM customers")).scalar_one()
    employees = db.execute(text("SELECT COUNT(*) FROM employees")).scalar_one()

    logger.info(f"Demo data: reseeded {orders} orders, {customers} customers")
    return {
        "removed_rows": sum(removed.values()),
        "orders": orders,
        "customers": customers,
        "employees": employees,
    }
