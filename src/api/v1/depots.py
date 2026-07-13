"""src/api/v1/depots.py — full CRUD for depots, company-scoped."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models import Depot
from src.db.repositories.depot import DepotRepository
from src.db.repositories.location import LocationRepository
from src.api.v1.deps import get_current_user, CurrentUser
from src.exceptions.common import EntityNotFound
from src.core.enums import LocationTypes
from src.schemas.depot import DepotOut, DepotCreate, DepotUpdate

router = APIRouter(prefix="/v1/depots", tags=["depots"])


def _to_out(db: Session, d: Depot) -> DepotOut:
    loc = LocationRepository(db).get(d.location_id) if d.location_id else None
    return DepotOut(
        id=d.id, name=d.name, company_id=d.company_id,
        operational_status=d.operational_status.value if d.operational_status else None,
        location_id=d.location_id,
        lat=loc.lat if loc else None, lng=loc.lng if loc else None,
        address_text=loc.address_text if loc else None,
    )


@router.get("", response_model=list[DepotOut])
def list_depots(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_to_out(db, d) for d in DepotRepository(db).list(current.company_id)]


@router.get("/{depot_id}", response_model=DepotOut)
def get_depot(depot_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    d = DepotRepository(db).get(depot_id, current.company_id)
    if d is None:
        raise EntityNotFound("depot", depot_id)
    return _to_out(db, d)


@router.post("", response_model=DepotOut, status_code=201)
def create_depot(body: DepotCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    loc = LocationRepository(db).create(body.lat, body.lng, current.user_id,
                                        type_=LocationTypes.company_depot, address_text=body.address_text)
    d = DepotRepository(db).create({"name": body.name, "location_id": loc.id},
                                   current.user_id, current.company_id)
    return _to_out(db, d)


@router.put("/{depot_id}", response_model=DepotOut)
def update_depot(depot_id: int, body: DepotUpdate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = DepotRepository(db)
    d = repo.get(depot_id, current.company_id)
    if d is None:
        raise EntityNotFound("depot", depot_id)
    if body.lat is not None and body.lng is not None:
        loc_repo = LocationRepository(db)
        if d.location_id:
            loc_repo.update_coords(loc_repo.get(d.location_id), body.lat, body.lng, current.user_id, body.address_text)
        else:
            loc = loc_repo.create(body.lat, body.lng, current.user_id,
                                  type_=LocationTypes.company_depot, address_text=body.address_text)
            d.location_id = loc.id
    d = repo.update(d, body.model_dump(exclude_unset=True, exclude={"lat", "lng", "address_text"}), current.user_id)
    return _to_out(db, d)


@router.delete("/{depot_id}", status_code=204)
def delete_depot(depot_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = DepotRepository(db)
    d = repo.get(depot_id, current.company_id)
    if d is None:
        raise EntityNotFound("depot", depot_id)
    repo.soft_delete(d, current.user_id)
