"""
src/utils/scripts/generate_synthetic_instance.py

Generate a synthetic routing instance for the ALNS engine.

Two modes:
  * default        -> build an in-memory ProblemData (HaversineProvider, no DB
                      writes) and print a summary. Fast, safe, good for unit
                      tests and quick inspection.
  * --seed-db      -> ALSO seed the dev DB with a company + depot + orders +
                      workers + vehicles + drivers, then load them back through
                      the real ``load_problem_data`` path to prove the DB loader.

Examples:
    python -m src.utils.scripts.generate_synthetic_instance --n-orders 20 --n-workers 4 --seed 42
    python -m src.utils.scripts.generate_synthetic_instance --service-type technician
    python -m src.utils.scripts.generate_synthetic_instance --seed-db
"""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, time, timedelta

from src.core.enums import (
    ServiceType, NurseClinicalSkill, TechnicianSkills, VehicleType, FuelType,
    OrderStatus,
)
from src.services.alns.problem_data import (
    ProblemData, HaversineProvider, NodeRef, OrderInfo, WorkerInfo,
    VehicleInfo, DriverInfo, build_travel_stack, day_type_for,
)
from src.core.config import settings

# Karachi-ish bounding box to scatter synthetic locations in
_LAT_MIN, _LAT_MAX = 24.78, 24.95
_LNG_MIN, _LNG_MAX = 66.95, 67.15
_DEPOT_LAT, _DEPOT_LNG = 24.8607, 67.0011   # roughly central Karachi

_SKILL_POOL = {
    ServiceType.nurse: [s.value for s in NurseClinicalSkill],
    ServiceType.technician: [s.value for s in TechnicianSkills],
}


# ---------------------------------------------------------------------------
# Skill assignment
# ---------------------------------------------------------------------------

def _cover_pool_skills(rng, pool: list[str], n_workers: int) -> list[list[str]]:
    """
    Assign skills to workers so the workforce COLLECTIVELY covers every skill in
    the pool (when n_workers permits), and each worker holds a realistic 2-3
    skills. This keeps synthetic instances mostly-serviceable — important for a
    meaningful demo, where we want the solver to actually optimize rather than
    just report everything as unserved.
    """
    sets: list[set[str]] = [set() for _ in range(n_workers)]
    # 1. spread the pool across workers round-robin so every skill is covered
    shuffled = list(pool)
    rng.shuffle(shuffled)
    for i, skill in enumerate(shuffled):
        sets[i % n_workers].add(skill)
    # 2. top each worker up to ~2-3 skills for redundancy
    for s in sets:
        target = min(len(pool), rng.randint(2, 3))
        while len(s) < target:
            s.add(rng.choice(pool))
    return [sorted(s) for s in sets]


# ---------------------------------------------------------------------------
# In-memory generation
# ---------------------------------------------------------------------------

def generate_in_memory(
    n_orders: int,
    n_workers: int,
    n_drivers: int,
    n_vehicles: int,
    service_type: ServiceType,
    seed: int,
    planned_date: date,
    active_hours=(8, 12, 17),
) -> ProblemData:
    """Build a self-contained ProblemData without touching the DB."""
    rng = random.Random(seed)
    pool = _SKILL_POOL[service_type]
    dtype = day_type_for(planned_date)

    # ---- nodes: depot + one per order --------------------------------------
    nodes = [NodeRef(0, 1, _DEPOT_LAT, _DEPOT_LNG, "depot_h3", is_depot=True)]
    orders: list[OrderInfo] = []
    for k in range(n_orders):
        lat = rng.uniform(_LAT_MIN, _LAT_MAX)
        lng = rng.uniform(_LNG_MIN, _LNG_MAX)
        idx = len(nodes)
        oid = k + 1
        nodes.append(NodeRef(idx, 100 + oid, lat, lng, f"order_h3_{oid}", order_id=oid))
        # each order needs 1 skill from the pool
        req = frozenset({rng.choice(pool)})
        dur_min = rng.choice([15, 30, 45, 60])
        orders.append(OrderInfo(
            id=oid, node_index=idx, required_skills=req,
            timewindow_start=None, timewindow_end=None,
            service_duration_sec=dur_min * 60,
            priority=rng.choice(["low", "normal", "high", "urgent"]),
            weight_kg=0.0, volume_m3=0.0,
        ))

    # ---- workers: skills chosen so the workforce COLLECTIVELY covers the pool
    # (otherwise many orders end up unserviceable, which makes a poor demo).
    worker_skill_sets = _cover_pool_skills(rng, pool, n_workers)
    workers: list[WorkerInfo] = []
    for w in range(n_workers):
        skills = frozenset(worker_skill_sets[w])
        workers.append(WorkerInfo(
            id=1000 + w, worker_type=service_type, skills=skills,
            shift_start=time(9, 0), shift_end=time(17, 0),
        ))

    # ---- vehicles ----------------------------------------------------------
    vehicles: list[VehicleInfo] = []
    for v in range(n_vehicles):
        vtype = rng.choice([VehicleType.car.value, VehicleType.van.value])
        ftype = rng.choice([FuelType.petrol.value, FuelType.diesel.value])
        vehicles.append(VehicleInfo(
            id=2000 + v, vehicle_type=vtype,
            seating_capacity=4 if vtype == VehicleType.van.value else 2,
            avg_speed_kmh=40, fuel_type=ftype, fuel_average=0.12,
            fuel_price=float(settings.FUEL_PRICES.get(ftype, 0.0)),
        ))

    # ---- drivers: eligible for car+van so any vehicle assignable -----------
    drivers: list[DriverInfo] = []
    for d in range(n_drivers):
        veh_id = vehicles[d % n_vehicles].id if n_vehicles else None
        drivers.append(DriverInfo(
            id=3000 + d, vehicle_id=veh_id,
            eligible_vehicle_types=frozenset({VehicleType.car.value, VehicleType.van.value}),
        ))

    stack, dist = build_travel_stack(nodes, HaversineProvider(avg_speed_kmh=40), dtype, active_hours)

    return ProblemData(
        company_id=1, planned_date=planned_date, service_type=service_type, day_type=dtype,
        nodes=nodes, depot_node_index=0, orders=orders, workers=workers,
        drivers=drivers, vehicles=vehicles,
        travel_time_sec=stack, distance_m=dist, active_hours=tuple(active_hours),
    )


def print_summary(pd: ProblemData) -> None:
    print("=" * 60)
    print("Synthetic ProblemData")
    print("=" * 60)
    print(f"  service_type : {pd.service_type.value}")
    print(f"  planned_date : {pd.planned_date}  ({pd.day_type.value})")
    print(f"  nodes        : {len(pd.nodes)}  (1 depot + {len(pd.orders)} orders)")
    print(f"  workers      : {len(pd.workers)}")
    print(f"  drivers      : {len(pd.drivers)}")
    print(f"  vehicles     : {len(pd.vehicles)}")
    print(f"  active_hours : {pd.active_hours}")
    # feasibility snapshot: how many workers can serve each order
    tight = 0
    for o in pd.orders:
        n_feasible = sum(1 for w in pd.workers if pd.worker_can_serve(w.id, o.id))
        if n_feasible == 0:
            tight += 1
    print(f"  orders with NO feasible worker : {tight}")
    # sample travel time depot -> first order at first active hour
    if pd.orders:
        h = pd.active_hours[0]
        t = pd.travel_time(0, pd.orders[0].node_index, h)
        d = pd.distance(0, pd.orders[0].node_index)
        print(f"  depot->order1 @ {h}h : {d:,.0f} m / {t:,.0f} s")
    print("=" * 60)


# ---------------------------------------------------------------------------
# DB seeding (opt-in)
# ---------------------------------------------------------------------------

def seed_db(
    n_orders: int, n_workers: int, n_drivers: int, n_vehicles: int,
    service_type: ServiceType, seed: int, planned_date: date,
) -> None:
    """
    Seed a synthetic company + related rows into the dev DB, then load them
    back through load_problem_data to exercise the real DB path.
    """
    from src.db.database import SessionLocal
    from src.db.models import (
        Company, Depot, Location, Order, Vehicle, Driver, Nurse, Technician, Employee,
        Customer,
    )
    from src.services.alns.problem_data import load_problem_data, HaversineProvider
    from src.core.enums import LocationTypes

    rng = random.Random(seed)
    pool = _SKILL_POOL[service_type]
    skill_enum = NurseClinicalSkill if service_type == ServiceType.nurse else TechnicianSkills

    db = SessionLocal()
    try:
        SYS = 1  # synthetic created_by

        company = Company(name=f"Synthetic {service_type.value.title()} Co",
                          service_type=service_type, created_by=SYS)
        db.add(company); db.flush()

        from src.services.h3_service import latlng_to_h3
        depot_loc = Location(type=LocationTypes.company_depot, lat=_DEPOT_LAT, lng=_DEPOT_LNG,
                             h3_index=latlng_to_h3(_DEPOT_LAT, _DEPOT_LNG), created_by=SYS)
        db.add(depot_loc); db.flush()
        depot = Depot(company_id=company.id, name="Synthetic Depot",
                     location_id=depot_loc.id, created_by=SYS)
        db.add(depot); db.flush()

        # one customer to own all synthetic orders (Order.customer_id is NOT NULL)
        customer = Customer(name="Synthetic Customer", company_id=company.id, created_by=SYS)
        db.add(customer); db.flush()

        # orders
        for k in range(n_orders):
            olat, olng = rng.uniform(_LAT_MIN, _LAT_MAX), rng.uniform(_LNG_MIN, _LNG_MAX)
            loc = Location(type=LocationTypes.customer_location,
                          lat=olat, lng=olng,
                          h3_index=latlng_to_h3(olat, olng), created_by=SYS)
            db.add(loc); db.flush()
            req = [skill_enum(rng.choice(pool))]
            o = Order(company_id=company.id, customer_id=customer.id, location_id=loc.id,
                     service_date=planned_date, status=OrderStatus.pending,
                     service_duration_min=rng.choice([15, 30, 45, 60]))
            if service_type == ServiceType.nurse:
                o.required_nurse_skills = req
            else:
                o.required_tech_skills = req
            db.add(o)

        # workers (employee + nurse/technician), skills chosen to collectively
        # cover the pool (same logic as the in-memory generator)
        WorkerModel = Nurse if service_type == ServiceType.nurse else Technician
        worker_skill_sets = _cover_pool_skills(rng, pool, n_workers)
        for w in range(n_workers):
            emp = Employee(name=f"Worker {w}", company_id=company.id,
                          shift_start=time(9, 0), shift_end=time(17, 0), created_by=SYS)
            db.add(emp); db.flush()
            skills = [skill_enum(s) for s in worker_skill_sets[w]]
            db.add(WorkerModel(employee_id=emp.id, skills=skills, created_by=SYS))

        # vehicles
        veh_ids = []
        for v in range(n_vehicles):
            vtype = rng.choice([VehicleType.car, VehicleType.van])
            veh = Vehicle(company_id=company.id, depot_id=depot.id,
                         license_plate=f"SYN-{v:03d}", type=vtype,
                         seating_capacity=4 if vtype == VehicleType.van else 2,
                         avg_speed_kmh=40, fuel_type=FuelType.petrol, fuel_average=0.12,
                         created_by=SYS)
            db.add(veh); db.flush()
            veh_ids.append(veh.id)

        # drivers
        for d in range(n_drivers):
            db.add(Driver(company_id=company.id, vehicle_id=veh_ids[d % len(veh_ids)] if veh_ids else None,
                         skills=[VehicleType.car, VehicleType.van], created_by=SYS))

        db.commit()
        print(f"Seeded company_id={company.id} into dev DB.")

        # load back through the real DB path (haversine to avoid OSMnx cost here)
        pd = load_problem_data(db, company.id, planned_date,
                               provider=HaversineProvider(avg_speed_kmh=40),
                               active_hours=(8, 12, 17))
        print("Loaded back via load_problem_data:")
        print_summary(pd)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Generate a synthetic ALNS routing instance.")
    p.add_argument("--n-orders", type=int, default=20)
    p.add_argument("--n-workers", type=int, default=4)
    p.add_argument("--n-drivers", type=int, default=3)
    p.add_argument("--n-vehicles", type=int, default=3)
    p.add_argument("--service-type", choices=["nurse", "technician"], default="nurse")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--date", type=str, default=None, help="planned date YYYY-MM-DD (default: tomorrow)")
    p.add_argument("--seed-db", action="store_true", help="also seed the dev DB and load back")
    args = p.parse_args()

    service_type = ServiceType(args.service_type)
    planned_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date else date.today() + timedelta(days=1)
    )

    pd = generate_in_memory(
        args.n_orders, args.n_workers, args.n_drivers, args.n_vehicles,
        service_type, args.seed, planned_date,
    )
    print_summary(pd)

    if args.seed_db:
        print("\n--seed-db set: seeding dev DB...\n")
        seed_db(args.n_orders, args.n_workers, args.n_drivers, args.n_vehicles,
                service_type, args.seed, planned_date)


if __name__ == "__main__":
    main()
