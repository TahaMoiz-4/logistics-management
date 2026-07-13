"""
src/api/v1/customers.py

Full CRUD for customers, company-scoped via auth. A customer may carry a location
(lat/lng -> Location row with h3). GET includes location + order count.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models import Customer
from src.db.repositories.customer import CustomerRepository
from src.db.repositories.location import LocationRepository
from src.api.v1.deps import get_current_user, CurrentUser
from src.exceptions.common import EntityNotFound
from src.core.enums import LocationTypes
from src.schemas.customer import CustomerOut, CustomerCreate, CustomerUpdate

router = APIRouter(prefix="/v1/customers", tags=["customers"])


def _to_out(db: Session, repo: CustomerRepository, c: Customer) -> CustomerOut:
    loc = None
    if c.location_id:
        loc = LocationRepository(db).get(c.location_id)
    return CustomerOut(
        id=c.id, name=c.name, company_id=c.company_id,
        contact_email=c.contact_email, contact_phone=c.contact_phone,
        location_id=c.location_id,
        lat=loc.lat if loc else None, lng=loc.lng if loc else None,
        address_text=loc.address_text if loc else None,
        order_count=repo.order_count(c.id),
    )


@router.get("", response_model=list[CustomerOut])
def list_customers(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = CustomerRepository(db)
    return [_to_out(db, repo, c) for c in repo.list(current.company_id)]


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, current: CurrentUser = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    repo = CustomerRepository(db)
    c = repo.get(customer_id, current.company_id)
    if c is None:
        raise EntityNotFound("customer", customer_id)
    return _to_out(db, repo, c)


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(body: CustomerCreate, current: CurrentUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    repo = CustomerRepository(db)
    location_id = None
    if body.lat is not None and body.lng is not None:
        loc = LocationRepository(db).create(
            body.lat, body.lng, current.user_id,
            type_=LocationTypes.customer_location, address_text=body.address_text,
        )
        location_id = loc.id
    c = repo.create(
        {"name": body.name, "contact_email": body.contact_email,
         "contact_phone": body.contact_phone, "location_id": location_id},
        current.user_id, current.company_id,
    )
    return _to_out(db, repo, c)


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, body: CustomerUpdate,
                    current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = CustomerRepository(db)
    c = repo.get(customer_id, current.company_id)
    if c is None:
        raise EntityNotFound("customer", customer_id)
    # location update/create
    if body.lat is not None and body.lng is not None:
        loc_repo = LocationRepository(db)
        if c.location_id:
            loc = loc_repo.get(c.location_id)
            loc_repo.update_coords(loc, body.lat, body.lng, current.user_id, body.address_text)
        else:
            loc = loc_repo.create(body.lat, body.lng, current.user_id,
                                  type_=LocationTypes.customer_location, address_text=body.address_text)
            c.location_id = loc.id
    fields = body.model_dump(exclude_unset=True, exclude={"lat", "lng", "address_text"})
    c = repo.update(c, fields, current.user_id)
    return _to_out(db, repo, c)


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: int, current: CurrentUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    repo = CustomerRepository(db)
    c = repo.get(customer_id, current.company_id)
    if c is None:
        raise EntityNotFound("customer", customer_id)
    repo.soft_delete(c, current.user_id)
