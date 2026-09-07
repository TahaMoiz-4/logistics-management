"""
src/utils/scripts/seed_demo_dataset.py

Builds a realistic, demo-ready dataset for TWO companies in Karachi:

  * Company 1 "Aga Khan Home Care"  (admin1)  -> NURSE service
  * Company 2 "SysTech Field Services" (admin2) -> TECHNICIAN service

Per company it seeds:
  * 1 depot at Citi Tower, Shahra-e-Faisal, PECHS (shared head-office address)
  * 5 field workers (nurses / technicians) with realistic PK names, CNICs,
    contacts, skills, shifts, mobile logins (worker<emp_id> / "password")
  * 3 drivers (all male) each bound to 1 vehicle (Sindh-style plates)
  * 8 customers spread across real Karachi neighbourhoods (all on land)
  * ~36 orders, all status=pending, 3-6 per day across the next 10 WORKING days
    (weekends skipped), with within-day time windows and skill requirements
    matching the service type

Order dates are relative to the day you run this, so the route-plan picker -
which only lists orders from today onward - always has data to show. Re-run it
whenever the demo needs refreshing.

It does NOT create any dynamic/solver data (route plans, assignments, position
events) — those are produced live by the solver + mobile app during the demo.

Run the reset first if you want a clean slate:
    python -m src.utils.scripts.reset_tenant_data --yes
    python -m src.utils.scripts.seed_demo_dataset
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from src.db.database import SessionLocal
from src.db.models import (
    Company, SysUsers, UserCompany, Employee, Nurse, Technician, Driver,
    Vehicle, Depot, Customer, Location, Order,
)
from src.core.enums import (
    ServiceType, OperationalStatus, VehicleType, FuelType, OrderPriority,
    OrderStatus, LocationTypes, NurseClinicalSkill, TechnicianSkills,
)
from src.core.security import hash_password
from src.services.h3_service import latlng_to_h3

DEMO_PASSWORD = "password"
SEED = 42
random.seed(SEED)

# Shared head-office / depot address (per user's instruction, both companies).
CITI_TOWER_ADDR = ("Citi Tower, 33-A Shahra-e-Faisal, P.E.C.H.S Block 2 "
                   "Block 6 P.E.C.H.S., Karachi, 75400, Pakistan")
CITI_TOWER_LAT, CITI_TOWER_LNG = 24.8699, 67.0656

# Real Karachi neighbourhoods (lat, lng, area, road) — all on land, spread wide
# so routing is visually meaningful on the map.
KHI_AREAS = [
    (24.7975, 67.0530, "DHA Phase 5",           "Khayaban-e-Shahbaz"),
    (24.7960, 67.0720, "DHA Phase 6",           "Khayaban-e-Muhafiz"),
    (24.8110, 67.0300, "Clifton Block 4",       "Schon Circle"),
    (24.8180, 67.0250, "Clifton Block 2",       "Khayaban-e-Roomi"),
    (24.9210, 67.0960, "Gulshan-e-Iqbal Block 6","University Road"),
    (24.9280, 67.1010, "Gulshan-e-Iqbal Block 10-A","Rashid Minhas Road"),
    (24.8760, 67.0700, "Bahadurabad",           "Alamgir Road"),
    (24.8660, 67.0620, "PECHS Block 2",         "Tariq Road"),
    (24.9130, 67.0330, "Nazimabad No. 3",       "Nazimabad Road"),
    (24.9450, 67.0370, "North Nazimabad Block B","Shahrah-e-Noor Jehan"),
    (24.9250, 67.1330, "Gulistan-e-Johar Block 15","Johar Chowrangi"),
    (24.9930, 67.2050, "Malir Cantt",           "Malir Cantt Road"),
    (24.8330, 67.1370, "Korangi Industrial Area","Korangi Road"),
    (24.8720, 67.1330, "Shah Faisal Colony",    "Drigh Road"),
    (24.9360, 67.0790, "Federal B Area Block 16","Ancholi"),
    (24.8600, 67.0270, "Saddar",                "Zaibunnisa Street"),
    (24.8790, 67.0180, "Garden East",           "Britto Road"),
    (24.8500, 67.1900, "Landhi",                "Landhi Town"),
    (24.9160, 67.0990, "NIPA Chowrangi",        "Aisha Bawany Road"),
    (24.8790, 66.9970, "SITE Area",             "Manghopir Road"),
]

FEMALE_NAMES = [
    "Ayesha Siddiqui", "Fatima Khan", "Sana Malik", "Hina Abbasi", "Rabia Qureshi",
    "Zainab Ali", "Maria Shaikh", "Nida Farooq", "Sadia Iqbal", "Komal Hussain",
]
MALE_NAMES = [
    "Bilal Ahmed", "Usman Raza", "Kashif Mehmood", "Adnan Sheikh", "Faisal Nawaz",
    "Imran Baloch", "Waqar Younis", "Salman Yousuf", "Danish Aziz", "Zeeshan Haider",
    "Asif Jamil", "Nabeel Anwar", "Owais Khan", "Tariq Mehmood", "Junaid Akram",
]

# Customer names. Kept separate from the staff pools above so a patient and a
# nurse never share a name in the demo.
#
# The two companies need different KINDS of name: company 1's customers are
# patients (people), company 2's are business premises (sites).
PATIENT_NAMES = [
    "Amina Rashid", "Ghulam Abbas", "Shazia Parveen", "Iqbal Hussain",
    "Naseem Akhtar", "Abdul Sattar", "Yasmin Bibi", "Mohammad Younus",
    "Farhat Jabeen", "Rizwan Ahmed", "Shabana Kausar", "Ashraf Ali",
    "Rukhsana Begum", "Nadeem Siddiqui", "Talat Mahmood", "Parveen Akhtar",
]
SITE_NAMES = [
    "Ittehad Textiles", "Karachi Steel Works", "Meezan Trading Co.",
    "Pak Suzuki Dealership", "Habib Cash & Carry", "Indus Pharma",
    "Sindh Cotton Mills", "Al-Karam Packaging", "Descon Engineering",
    "Gul Ahmed Retail", "National Foods Depot", "Shaheen Logistics",
    "Unique Plastics", "Bahria Medical Centre", "Orient Electronics",
    "Sapphire Fibres",
]

VEHICLE_MODELS = [
    ("Toyota Hiace", VehicleType.van, "White", 2694, FuelType.petrol, 8.0, 12),
    ("Suzuki APV",   VehicleType.van, "Silver", 1493, FuelType.petrol, 11.0, 7),
    ("Toyota Corolla", VehicleType.car, "White", 1798, FuelType.petrol, 13.0, 4),
    ("Honda BR-V",   VehicleType.car, "Grey", 1497, FuelType.petrol, 12.0, 6),
    ("Suzuki Bolan", VehicleType.van, "White", 796, FuelType.cng, 14.0, 6),
]


def _mk_location(db, lat, lng, addr, loc_type) -> Location:
    loc = Location(
        type=loc_type, lat=lat, lng=lng,
        h3_index=latlng_to_h3(lat, lng), address_text=addr, created_by=1,
    )
    db.add(loc); db.flush()
    return loc


def _cnic() -> str:
    return f"42101-{random.randint(1000000,9999999)}-{random.randint(1,9)}"


def _mobile() -> str:
    return f"+9230{random.randint(0,9)}-{random.randint(1000000,9999999)}"


def _plate() -> str:
    # Sindh/Karachi style, e.g. "AKD-472", "BGT-1188", "JX-9021"
    letters = "".join(random.choice("ABCDEFGJKLMNPRSTUVWXYZ") for _ in range(random.choice([2, 3])))
    number = random.randint(100, 9999)
    return f"{letters}-{number}"


def _ensure_company(db, cid, name, service_type, ho_loc_id) -> Company:
    c = db.query(Company).filter(Company.id == cid).one_or_none()
    if c is None:
        c = Company(id=cid, name=name, service_type=service_type,
                    contact_number=_mobile(), contact_email=f"info@{name.split()[0].lower()}.pk",
                    timezone="Asia/Karachi", head_office_location_id=ho_loc_id, created_by=1)
        db.add(c); db.flush()
    else:
        c.name = name
        c.service_type = service_type
        c.head_office_location_id = ho_loc_id
    return c


def _ensure_sysuser(db, username, company_id):
    u = db.query(SysUsers).filter(SysUsers.username == username).one_or_none()
    if u is None:
        u = SysUsers(username=username, password_hash=hash_password(DEMO_PASSWORD),
                     role="admin", created_by=1)
        db.add(u); db.flush()
    else:
        u.password_hash = hash_password(DEMO_PASSWORD)
    if db.query(UserCompany).filter(UserCompany.user_id == u.id,
                                    UserCompany.company_id == company_id).one_or_none() is None:
        db.add(UserCompany(user_id=u.id, company_id=company_id, created_by=1))


def _seed_company(db, cid, name, service_type, admin_username):
    print(f"\n== Company {cid}: {name} ({service_type.value}) ==")

    # 1) Head-office location + depot (both at Citi Tower).
    ho_loc = _mk_location(db, CITI_TOWER_LAT, CITI_TOWER_LNG, CITI_TOWER_ADDR,
                          LocationTypes.company_head_office)
    _ensure_company(db, cid, name, service_type, ho_loc.id)
    _ensure_sysuser(db, admin_username, cid)

    depot_loc = _mk_location(db, CITI_TOWER_LAT, CITI_TOWER_LNG, CITI_TOWER_ADDR,
                             LocationTypes.company_depot)
    depot = Depot(company_id=cid, name=f"{name.split()[0]} Main Depot",
                  location_id=depot_loc.id, operational_status=OperationalStatus.active,
                  created_by=1)
    db.add(depot); db.flush()
    print(f"  depot @ Citi Tower (loc {depot_loc.id})")

    # 2) Field workers (5). Nurses mostly female; technicians male.
    is_nurse = service_type == ServiceType.nurse
    nurse_skills = list(NurseClinicalSkill)
    tech_skills = list(TechnicianSkills)
    female_pool = FEMALE_NAMES.copy(); random.shuffle(female_pool)
    male_pool = MALE_NAMES.copy(); random.shuffle(male_pool)

    worker_emp_ids = []
    for i in range(5):
        if is_nurse:
            # mostly female: 4 of 5 female
            female = i < 4
            person = female_pool.pop() if female else male_pool.pop()
        else:
            person = male_pool.pop()  # techs all male
        emp = Employee(
            name=person, contact_number=_mobile(),
            contact_email=f"{person.split()[0].lower()}.{cid}{i}@{name.split()[0].lower()}.pk",
            cnic=_cnic(), company_id=cid,
            shift_start=time(9, 0), shift_end=time(17, 0),
            operational_status=OperationalStatus.active, created_by=1,
        )
        db.add(emp); db.flush()
        emp.username = f"worker{emp.id}"
        emp.password_hash = hash_password(DEMO_PASSWORD)
        worker_emp_ids.append(emp.id)

        if is_nurse:
            skills = random.sample(nurse_skills, k=random.randint(2, 3))
            db.add(Nurse(employee_id=emp.id, orders_completed=random.randint(20, 300),
                         rating=round(random.uniform(3.8, 5.0), 1),
                         skills=skills, operational_status=OperationalStatus.active,
                         created_by=1))
        else:
            skills = random.sample(tech_skills, k=random.randint(2, 3))
            db.add(Technician(employee_id=emp.id, orders_completed=random.randint(20, 300),
                              rating=round(random.uniform(3.8, 5.0), 1),
                              skills=skills, operational_status=OperationalStatus.active,
                              created_by=1))
    print(f"  5 field workers (logins worker{worker_emp_ids[0]}..worker{worker_emp_ids[-1]})")

    # 3) Vehicles (3) + drivers (3, all male, one per vehicle).
    for i in range(3):
        model, vtype, color, cc, fuel, favg, seats = VEHICLE_MODELS[i % len(VEHICLE_MODELS)]
        veh = Vehicle(
            company_id=cid, depot_id=depot.id, license_plate=_plate(), type=vtype,
            model=model, color=color, engine_cc=cc,
            max_weight_kg=800 if vtype == VehicleType.van else 400,
            max_volume_m3=6.0 if vtype == VehicleType.van else 2.0,
            seating_capacity=seats, avg_speed_kmh=35, fuel_type=fuel, fuel_average=favg,
            monthly_maintenance_cost=random.randint(8000, 25000),
            operational_status=OperationalStatus.active, created_by=1,
        )
        db.add(veh); db.flush()

        drv_person = male_pool.pop()
        drv_emp = Employee(
            name=drv_person, contact_number=_mobile(),
            contact_email=f"{drv_person.split()[0].lower()}.drv{cid}{i}@{name.split()[0].lower()}.pk",
            cnic=_cnic(), company_id=cid, shift_start=time(8, 30), shift_end=time(17, 30),
            operational_status=OperationalStatus.active, created_by=1,
        )
        db.add(drv_emp); db.flush()
        drv_emp.username = f"worker{drv_emp.id}"
        drv_emp.password_hash = hash_password(DEMO_PASSWORD)
        db.add(Driver(
            company_id=cid, employee_id=drv_emp.id, vehicle_id=veh.id,
            drivers_license_number=f"SIND-{random.randint(100000,999999)}",
            orders_completed=random.randint(50, 500),
            kms_driven=round(random.uniform(5000, 60000), 1),
            rating=round(random.uniform(3.8, 5.0), 1),
            skills=[vtype], operational_status=OperationalStatus.active, created_by=1,
        ))
    print(f"  3 vehicles + 3 drivers (Sindh plates)")

    # 4) Customers (8) at spread-out KHI areas.
    #
    # Named as real people (nurse co: patients) or businesses (tech co: sites)
    # rather than "Patient - Clifton Block 2" — the area is already visible on
    # the map and in address_text, so putting it in the name told you nothing
    # and made the demo look like placeholder data.
    areas = random.sample(KHI_AREAS, k=8)
    name_pool = (PATIENT_NAMES if is_nurse else SITE_NAMES).copy()
    random.shuffle(name_pool)
    customers = []
    for idx, (lat, lng, area, road) in enumerate(areas):
        cust_loc = _mk_location(db, lat, lng, f"{road}, {area}, Karachi",
                                LocationTypes.customer_location)
        cust = Customer(
            name=name_pool[idx],
            company_id=cid, location_id=cust_loc.id,
            contact_phone=_mobile(),
            contact_email=f"contact{idx}@{name.split()[0].lower()}-cust.pk",
            created_by=1,
        )
        db.add(cust); db.flush()
        customers.append((cust, cust_loc, area))
    print(f"  8 customers across KHI")

    # 5) Orders, spread over the next N working days, all pending.
    #
    # Dates are RELATIVE to today, not absolute. GET /v1/orders/servable - the
    # route-plan order picker - only returns orders with
    # service_date >= today (see OrderRepository.list_servable). A hardcoded
    # window silently falls out of range once the calendar passes it: the orders
    # still show on the orders page, but the picker comes up empty with no
    # error anywhere.
    #
    # Starting tomorrow (not today) keeps every order genuinely schedulable -
    # a same-day 09:00 window is already in the past if you demo after lunch.
    start = date.today() + timedelta(days=1)
    per_day = [5, 4, 4, 4, 3, 6, 4, 3, 4, 3]
    order_count = 0

    # One service date per entry in per_day, skipping weekends. Note this cannot
    # be `start + timedelta(days=d_idx)`: skipped Sat/Sun push later dates
    # further out, so the loop index and the calendar offset diverge.
    svc_dates = []
    d = start
    while len(svc_dates) < len(per_day):
        if d.weekday() < 5:          # Mon-Fri (weekday(): Mon=0 .. Sun=6)
            svc_dates.append(d)
        d += timedelta(days=1)

    for d_idx, n in enumerate(per_day):
        svc_date = svc_dates[d_idx]
        for _ in range(n):
            cust, cust_loc, area = random.choice(customers)
            # a within-day time window inside the 9-17 shift
            tw_start_hr = random.choice([9, 10, 11, 13, 14, 15])
            tw_start = datetime.combine(svc_date, time(tw_start_hr, 0))
            tw_end = tw_start + timedelta(hours=2)
            if is_nurse:
                req_nurse = random.sample(list(NurseClinicalSkill), k=1)
                req_tech = None
                svc_name = random.choice(["Home Nursing Visit", "Wound Dressing",
                                          "IV Therapy", "Blood Sample Collection",
                                          "Post-op Care", "Elderly Care Visit"])
            else:
                req_nurse = None
                req_tech = random.sample(list(TechnicianSkills), k=1)
                svc_name = random.choice(["Router Installation", "Network Setup",
                                          "Hardware Repair", "Cabling Job",
                                          "System Configuration", "On-site Diagnostics"])
            db.add(Order(
                name=f"{svc_name} - {area}",
                company_id=cid, customer_id=cust.id, location_id=cust_loc.id,
                weight_kg=round(random.uniform(0.5, 8.0), 1),
                volume_m3=round(random.uniform(0.01, 0.2), 3),
                required_nurse_skills=req_nurse, required_tech_skills=req_tech,
                service_date=svc_date, timewindow_start=tw_start, timewindow_end=tw_end,
                service_duration_min=random.choice([20, 30, 45, 60]),
                priority=random.choices(
                    [OrderPriority.normal, OrderPriority.high, OrderPriority.urgent],
                    weights=[6, 3, 1])[0],
                status=OrderStatus.pending, created_by=1,
            ))
            order_count += 1
    print(f"  {order_count} orders over {len(svc_dates)} working days, "
          f"{svc_dates[0]:%a %d %b} - {svc_dates[-1]:%a %d %b %Y} (all pending)")


def main():
    db = SessionLocal()
    try:
        print("Seeding demo dataset (Karachi)...")
        _seed_company(db, 1, "Aga Khan Home Care", ServiceType.nurse, "admin1")
        _seed_company(db, 2, "SysTech Field Services", ServiceType.technician, "admin2")
        db.commit()
        print("\nDone. Web: admin1 / admin2 (password='password').")
        print("Mobile: worker<employee_id> / 'password' — check the workers page for ids.")
    except Exception:
        db.rollback()
        print("ERROR — rolled back, nothing seeded.")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
