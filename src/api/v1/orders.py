"""
src/api/v1/orders.py

Full CRUD for orders (company-scoped via auth), plus the "servable" listing used
by the route-plan order picker.

  GET  /v1/orders            -> all orders (admin history/management view)
  GET  /v1/orders/servable   -> pending/assigned orders today-onward (picker)
  GET  /v1/orders/{id}
  POST /v1/orders            -> create (with location by id or lat/lng)
  PUT  /v1/orders/{id}
  DELETE /v1/orders/{id}
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models import Company, Order, Location, Customer
from src.db.repositories.order import OrderRepository
from src.db.repositories.location import LocationRepository
from src.api.v1.deps import get_current_user, CurrentUser
from src.exceptions.common import EntityNotFound, ValidationFailed
from src.core.enums import OrderStatus, OrderPriority, ServiceType, LocationTypes, NurseClinicalSkill, TechnicianSkills
from src.schemas.route_plan import ServableOrderOut
from src.schemas.order import OrderOut, OrderCreate, OrderUpdate

router = APIRouter(prefix="/v1/orders", tags=["orders"])

_SERVABLE = (OrderStatus.pending, OrderStatus.assigned)


# ── helpers ──────────────────────────────────────────────────────────────────

def _service_type(db: Session, company_id: int) -> ServiceType:
    c = db.query(Company).filter(Company.id == company_id).first()
    return (c.service_type if c else None) or ServiceType.nurse


def _coerce_skills(st: ServiceType, skills: list[str]):
    enum = NurseClinicalSkill if st == ServiceType.nurse else TechnicianSkills
    out = []
    for s in skills or []:
        try:
            out.append(enum(s))
        except ValueError:
            raise ValidationFailed(f"invalid skill '{s}' for {st.value}")
    return out


def _to_out(db: Session, o: Order) -> OrderOut:
    loc = db.query(Location).filter(Location.id == o.location_id).first() if o.location_id else None
    cust = db.query(Customer).filter(Customer.id == o.customer_id).first()
    return OrderOut(
        id=o.id, name=o.name, company_id=o.company_id, customer_id=o.customer_id,
        customer_name=cust.name if cust else None,
        customer_phone=cust.contact_phone if cust else None,
        location_id=o.location_id,
        lat=loc.lat if loc else None, lng=loc.lng if loc else None,
        address_text=loc.address_text if loc else None,
        status=o.status.value if o.status else "pending",
        priority=o.priority.value if o.priority else "normal",
        service_date=o.service_date,
        timewindow_start=o.timewindow_start, timewindow_end=o.timewindow_end,
        service_duration_min=o.service_duration_min,
        required_nurse_skills=[s.value if hasattr(s, "value") else str(s) for s in (o.required_nurse_skills or [])],
        required_tech_skills=[s.value if hasattr(s, "value") else str(s) for s in (o.required_tech_skills or [])],
        weight_kg=float(o.weight_kg) if o.weight_kg is not None else None,
        volume_m3=float(o.volume_m3) if o.volume_m3 is not None else None,
        notes=o.notes, created_at=o.created_at,
    )


# ── servable picker list ─────────────────────────────────────────────────────

@router.get("/servable", response_model=list[ServableOrderOut])
def list_servable_orders(
    from_date: date | None = Query(None, description="earliest service_date (default: today)"),
    to_date: date | None = Query(None, description="latest service_date (default: unbounded)"),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pending/assigned orders, today-onward, for the route-plan order picker."""
    st = _service_type(db, current.company_id)
    orders = OrderRepository(db).list_servable(
        current.company_id, from_date=from_date or date.today(), to_date=to_date,
    )
    loc_ids = {o.location_id for o in orders if o.location_id}
    locs = {l.id: l for l in db.query(Location).filter(Location.id.in_(loc_ids)).all()} if loc_ids else {}
    out = []
    for o in orders:
        raw = (o.required_nurse_skills if st == ServiceType.nurse else o.required_tech_skills) or []
        loc = locs.get(o.location_id)
        out.append(ServableOrderOut(
            id=o.id, name=o.name, customer_id=o.customer_id, service_date=o.service_date,
            status=o.status.value if o.status else "pending",
            priority=o.priority.value if o.priority else "normal",
            required_skills=[s.value if hasattr(s, "value") else str(s) for s in raw],
            timewindow_start=o.timewindow_start, timewindow_end=o.timewindow_end,
            service_duration_min=o.service_duration_min,
            lat=loc.lat if loc else None, lng=loc.lng if loc else None,
            address_text=loc.address_text if loc else None,
        ))
    return out


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[OrderOut])
def list_orders(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_to_out(db, o) for o in OrderRepository(db).list(current.company_id)]


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    o = OrderRepository(db).get(order_id, current.company_id)
    if o is None:
        raise EntityNotFound("order", order_id)
    return _to_out(db, o)


@router.post("", response_model=OrderOut, status_code=201)
def create_order(body: OrderCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    st = _service_type(db, current.company_id)
    # validate customer
    cust = db.query(Customer).filter(Customer.id == body.customer_id, Customer.company_id == current.company_id).first()
    if cust is None:
        raise ValidationFailed(f"customer {body.customer_id} not found for this company")
    # resolve location
    location_id = body.location_id
    if location_id is None and body.lat is not None and body.lng is not None:
        loc = LocationRepository(db).create(body.lat, body.lng, current.user_id,
                                            type_=LocationTypes.customer_location, address_text=body.address_text)
        location_id = loc.id
    if location_id is None:
        raise ValidationFailed("order requires a location (location_id or lat/lng)")

    data = {
        "customer_id": body.customer_id, "location_id": location_id,
        "service_date": body.service_date, "name": body.name,
        "status": OrderStatus.pending,
        "priority": OrderPriority(body.priority) if body.priority else OrderPriority.normal,
        "timewindow_start": body.timewindow_start, "timewindow_end": body.timewindow_end,
        "service_duration_min": body.service_duration_min,
        "weight_kg": body.weight_kg, "volume_m3": body.volume_m3, "notes": body.notes,
    }
    skills = _coerce_skills(st, body.required_skills)
    if st == ServiceType.nurse:
        data["required_nurse_skills"] = skills
    else:
        data["required_tech_skills"] = skills
    o = OrderRepository(db).create(data, current.user_id, current.company_id)
    return _to_out(db, o)


@router.put("/{order_id}", response_model=OrderOut)
def update_order(order_id: int, body: OrderUpdate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = OrderRepository(db)
    o = repo.get(order_id, current.company_id)
    if o is None:
        raise EntityNotFound("order", order_id)
    st = _service_type(db, current.company_id)
    data = body.model_dump(exclude_unset=True)

    # location update
    if data.get("lat") is not None and data.get("lng") is not None:
        loc_repo = LocationRepository(db)
        if o.location_id:
            loc_repo.update_coords(loc_repo.get(o.location_id), data["lat"], data["lng"], current.user_id, data.get("address_text"))
        else:
            loc = loc_repo.create(data["lat"], data["lng"], current.user_id,
                                  type_=LocationTypes.customer_location, address_text=data.get("address_text"))
            o.location_id = loc.id
    for k in ("lat", "lng", "address_text"):
        data.pop(k, None)

    if data.get("status"):
        o.status = OrderStatus(data.pop("status"))
    if data.get("priority"):
        o.priority = OrderPriority(data.pop("priority"))
    if "required_skills" in data and data["required_skills"] is not None:
        skills = _coerce_skills(st, data.pop("required_skills"))
        if st == ServiceType.nurse:
            o.required_nurse_skills = skills
        else:
            o.required_tech_skills = skills
    o = repo.update(o, data, current.user_id)
    return _to_out(db, o)


@router.delete("/{order_id}", status_code=204)
def delete_order(order_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = OrderRepository(db)
    o = repo.get(order_id, current.company_id)
    if o is None:
        raise EntityNotFound("order", order_id)
    repo.soft_delete(o, current.user_id)
