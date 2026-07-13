"""
src/api/v1/auth.py

Web (SysUser) authentication: login, logout, me.

Login verifies the bcrypt password and issues an hmac-signed token embedding the
operator's id + company. Logout is stateless (client drops the token) — there's
no server-side token store yet; documented as a future hardening item.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.core.security import verify_password, issue_token, SUBJECT_SYSUSER
from src.db.repositories.sys_users import SysUserRepository
from src.api.v1.deps import get_current_user, CurrentUser
from src.exceptions.auth import InvalidCredentials
from src.schemas.auth import LoginRequest, LoginResponse, SysUserOut

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    repo = SysUserRepository(db)
    user = repo.get_by_username(body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise InvalidCredentials()

    company_id = repo.company_id_for(user.id)
    if company_id is None:
        # a system operator with no company link can't be scoped — treat as bad login
        raise InvalidCredentials()

    token = issue_token(user.id, SUBJECT_SYSUSER, company_id)
    return LoginResponse(
        token=token,
        user=SysUserOut(
            id=user.id, username=user.username, role=user.role,
            company_id=company_id, contact_email=user.primary_contact_email,
            contact_number=user.primary_contact_number,
        ),
    )


@router.post("/logout")
def logout(current: CurrentUser = Depends(get_current_user)):
    # stateless token — nothing to revoke server-side yet. Endpoint exists so the
    # client has a definite "logged out" signal and for future token revocation.
    return {"status": "logged_out"}


@router.get("/me", response_model=SysUserOut)
def me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = SysUserRepository(db).get(current.user_id)
    return SysUserOut(
        id=user.id, username=user.username, role=user.role,
        company_id=current.company_id, contact_email=user.primary_contact_email,
        contact_number=user.primary_contact_number,
    )
