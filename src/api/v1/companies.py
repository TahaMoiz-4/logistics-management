"""
src/api/v1/companies.py

The caller's own company: view + update. No create/delete — companies are
tenant fixtures. company_id always comes from auth.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.repositories.company import CompanyRepository
from src.api.v1.deps import get_current_user, CurrentUser
from src.exceptions.common import EntityNotFound
from src.schemas.company import CompanyOut, CompanyUpdate

router = APIRouter(prefix="/v1/company", tags=["company"])


def _to_out(c) -> CompanyOut:
    return CompanyOut(
        id=c.id, name=c.name,
        service_type=c.service_type.value if c.service_type else None,
        contact_number=c.contact_number, contact_email=c.contact_email,
        timezone=c.timezone, head_office_location_id=c.head_office_location_id,
    )


@router.get("", response_model=CompanyOut)
def get_my_company(current: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    c = CompanyRepository(db).get(current.company_id)
    if c is None:
        raise EntityNotFound("company", current.company_id)
    return _to_out(c)


@router.put("", response_model=CompanyOut)
def update_my_company(body: CompanyUpdate,
                      current: CurrentUser = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    repo = CompanyRepository(db)
    c = repo.get(current.company_id)
    if c is None:
        raise EntityNotFound("company", current.company_id)
    c = repo.update(c, body.model_dump(exclude_unset=True), current.user_id)
    return _to_out(c)
