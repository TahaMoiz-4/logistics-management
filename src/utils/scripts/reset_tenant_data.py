"""
src/utils/scripts/reset_tenant_data.py

Empties all COMPANY / USER operational data from the database while preserving:
  * companies       — the tenants themselves (so admins can log straight back in)
  * sys_users       — web admin/operator logins
  * users_companies — the admin->company bindings (kept so logins keep working;
                      without these an admin resolves to no company and login fails)
  * zones           — H3 reference geometry
  * traffic_profiles — synthetic traffic reference data

Everything a tenant *accumulates* (orders, plans, routes, workers, vehicles,
depots, customers, positions, device tokens, and the location rows those own)
is truncated. After running you have empty companies + admins, ready to re-seed
depots/employees/orders and re-run the solver.

Usage:
    python -m src.utils.scripts.reset_tenant_data          # interactive (asks to confirm)
    python -m src.utils.scripts.reset_tenant_data --yes    # skip the prompt

All deletes run in ONE transaction — if anything fails, nothing is committed.
"""

from __future__ import annotations

import sys

from sqlalchemy import text

from src.db.database import SessionLocal


# Deleted in this exact order: children before parents, because every FK is a
# plain reference (no ON DELETE CASCADE) — a wrong order raises a FK violation.
# `locations` is last and needs companies.head_office_location_id nulled first
# (companies are kept but point into the location rows we're clearing).
DELETE_ORDER = [
    # leaf-most execution/tracking rows
    "worker_assignment_stops",
    "driver_route_stops",
    "vehicle_position_events",
    "worker_position_events",
    "device_tokens",
    # assignment / routing layer
    "worker_assignments",
    "driver_routes",
    "route_plans",
    # orders reference customers + locations
    "orders",
    # worker role rows reference employees (drivers also -> vehicles)
    "drivers",
    "nurses",
    "technicians",
    # fleet + facilities + people + membership
    "vehicles",
    "depots",
    "customers",
    "employees",
    # addresses, cleared last
    "locations",
]

# Explicitly preserved — listed here so the summary can show what survives.
# users_companies stays so admins keep their company binding (and can log in).
PRESERVED = ["companies", "sys_users", "users_companies", "zones", "traffic_profiles"]


def _count(session, table: str) -> int:
    return session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def main() -> None:
    skip_prompt = "--yes" in sys.argv or "-y" in sys.argv

    session = SessionLocal()
    try:
        # Snapshot current row counts so the user sees exactly what will go.
        counts = {t: _count(session, t) for t in DELETE_ORDER}
        preserved_counts = {t: _count(session, t) for t in PRESERVED}
        total = sum(counts.values())

        print("\n=== reset_tenant_data ===")
        print("\nWILL DELETE (child -> parent order):")
        for t in DELETE_ORDER:
            print(f"  {t:26} {counts[t]:>8} rows")
        print(f"  {'TOTAL':26} {total:>8} rows")

        print("\nWILL PRESERVE:")
        for t in PRESERVED:
            print(f"  {t:26} {preserved_counts[t]:>8} rows")

        if total == 0:
            print("\nNothing to delete — all target tables already empty.")
            return

        if not skip_prompt:
            print()
            answer = input("Type 'yes' to permanently delete the above: ").strip()
            if answer != "yes":
                print("Aborted — nothing was deleted.")
                return

        # One transaction: null the kept-tables' refs into locations, then delete
        # children before parents. Any error rolls the whole thing back.
        session.execute(text("UPDATE companies SET head_office_location_id = NULL"))
        deleted = {}
        for t in DELETE_ORDER:
            res = session.execute(text(f"DELETE FROM {t}"))
            deleted[t] = res.rowcount

        # Restart each emptied table's identity sequence so a following re-seed
        # produces clean, predictable ids (employees start at 1 -> worker1, ...).
        # RESTART IDENTITY on a per-table basis; wrapped in try so a table whose
        # PK isn't a serial/identity (none here) wouldn't abort the reset.
        for t in DELETE_ORDER:
            session.execute(text(
                f'ALTER SEQUENCE IF EXISTS {t}_id_seq RESTART WITH 1'))
        session.commit()

        print("\nDeleted:")
        for t in DELETE_ORDER:
            print(f"  {t:26} {deleted[t]:>8} rows")
        print("\nDone. companies + sys_users + zones + traffic_profiles preserved.")

    except Exception:
        session.rollback()
        print("\nERROR — transaction rolled back, nothing was deleted.")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
