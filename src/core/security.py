"""
src/core/security.py

Auth primitives: password hashing (bcrypt) and a small hmac-signed token
(stdlib only, no JWT library).

Token format:  base64url(payload_json) + "." + base64url(hmac_sha256(payload))
payload = {"sub": <id>, "typ": "sysuser"|"employee", "cid": <company_id>, "iat": <ts>}

No expiry yet (documented gap). Signed with settings.SECRET_KEY so it cannot be
forged; the server is stateless — it re-verifies the signature on every request.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time as _time
from typing import Optional

import bcrypt

from src.core.config import settings

# subject types embedded in the token
SUBJECT_SYSUSER = "sysuser"
SUBJECT_EMPLOYEE = "employee"


# ---------------------------------------------------------------------------
# Password hashing (bcrypt)
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: Optional[str]) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Token issue / verify
# ---------------------------------------------------------------------------

def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(payload_b64: str) -> str:
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64e(sig)


def issue_token(subject_id: int, subject_type: str, company_id: int) -> str:
    payload = {
        "sub": subject_id,
        "typ": subject_type,
        "cid": company_id,
        "iat": int(_time.time()),
    }
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_token(token: str) -> Optional[dict]:
    """
    Return the decoded payload dict if the token is well-formed and the
    signature checks out, else None. Constant-time signature comparison.
    """
    if not token or "." not in token:
        return None
    payload_b64, sig = token.rsplit(".", 1)
    expected = _sign(payload_b64)
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        return json.loads(_b64d(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
