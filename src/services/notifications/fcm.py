"""
src/services/notifications/fcm.py

Push-notification service. Sends "new/changed job" alerts to a worker's
registered devices (FCM tokens in the device_tokens table) when a plan is
approved.

Two modes, chosen by whether Firebase credentials are configured:
  * STUB (default): logs the intended push (tokens + payload) but sends nothing.
    Used until FIREBASE credentials are wired.
  * REAL: sends via FCM HTTP v1 (google.oauth2 service account). The single
    real-send call site is marked below.

The rest of the system calls notify_workers(...) regardless of mode.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

import requests
from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.repositories.device_token import DeviceTokenRepository

logger = logging.getLogger(__name__)

_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_FCM_TIMEOUT_SEC = 10

# Cached service-account credentials, built once and reused across sends.
# google.auth.Credentials refreshes its own OAuth access token when expired,
# so we avoid re-reading the key file + re-doing the token exchange per push.
_creds = None
_creds_lock = threading.Lock()


def _fcm_configured() -> bool:
    """True if a Firebase service-account path + project id are configured."""
    return bool(
        getattr(settings, "FIREBASE_CREDENTIALS_PATH", None)
        and getattr(settings, "FIREBASE_PROJECT_ID", None)
    )


def _get_credentials():
    """Build (once) and return the cached service-account Credentials."""
    global _creds
    if _creds is None:
        with _creds_lock:
            if _creds is None:
                from google.oauth2 import service_account

                _creds = service_account.Credentials.from_service_account_file(
                    settings.FIREBASE_CREDENTIALS_PATH, scopes=[_FCM_SCOPE]
                )
    return _creds


def _access_token() -> str:
    """A valid OAuth2 bearer token, refreshing the cached credentials if stale."""
    from google.auth.transport.requests import Request as GoogleRequest

    creds = _get_credentials()
    if not creds.valid:
        creds.refresh(GoogleRequest())
    return creds.token


def notify_workers(
    db: Session,
    employee_ids: list[int],
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> dict:
    """
    Send a push to each employee's active devices. Returns a summary dict
    {sent, skipped, mode}. Never raises — a notification failure must not break
    the calling flow (e.g. plan approval).
    """
    repo = DeviceTokenRepository(db)
    tokens: list[str] = []
    for emp_id in employee_ids:
        tokens.extend(repo.active_tokens_for(emp_id))

    if not tokens:
        logger.info(f"notify_workers: no device tokens for employees {employee_ids}")
        return {"sent": 0, "skipped": len(employee_ids), "mode": "none"}

    if not _fcm_configured():
        # STUB MODE — no Firebase creds yet.
        logger.info(
            f"[FCM STUB] would push to {len(tokens)} device(s) for employees "
            f"{employee_ids}: title={title!r} body={body!r} data={data}"
        )
        return {"sent": 0, "skipped": len(tokens), "mode": "stub",
                "would_send_to": len(tokens)}

    # REAL MODE — send via FCM HTTP v1. Build the OAuth token once for the batch;
    # if even that fails (bad key file, no network) bail without breaking caller.
    try:
        bearer = _access_token()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"FCM auth failed, dropping push for {employee_ids}: {exc}")
        return {"sent": 0, "skipped": len(tokens), "mode": "real", "error": "auth"}

    sent = 0
    pruned = 0
    for token in tokens:
        try:
            _send_fcm_v1(bearer, token, title, body, data or {})
            sent += 1
        except _DeadToken:
            # FCM says this token is gone — deactivate so we stop retrying it.
            repo.deactivate(token)
            pruned += 1
            logger.info("FCM: deactivated a stale/unregistered device token")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"FCM send failed for a token: {exc}")
    return {"sent": sent, "skipped": len(tokens) - sent, "pruned": pruned,
            "mode": "real"}


class _DeadToken(Exception):
    """Raised when FCM reports a token is unregistered/invalid (should be pruned)."""


def _send_fcm_v1(bearer: str, token: str, title: str, body: str, data: dict) -> None:
    """
    THE single real-send call site. Sends one FCM HTTP v1 message using an
    already-obtained OAuth bearer token.

    Raises _DeadToken when FCM reports the token is unregistered/invalid so the
    caller can deactivate it; raises for any other HTTP/transport error.
    """
    url = f"https://fcm.googleapis.com/v1/projects/{settings.FIREBASE_PROJECT_ID}/messages:send"
    message = {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
            # FCM data values must be strings.
            "data": {k: str(v) for k, v in data.items()},
        }
    }
    resp = requests.post(
        url, json=message,
        headers={"Authorization": f"Bearer {bearer}",
                 "Content-Type": "application/json"},
        timeout=_FCM_TIMEOUT_SEC,
    )

    if resp.status_code == 200:
        return

    # An unregistered/invalid token: 404 UNREGISTERED or 400 INVALID_ARGUMENT
    # on the token field. Signal the caller to prune it.
    if resp.status_code in (404, 400):
        err = ""
        try:
            err = resp.json().get("error", {}).get("status", "")
        except Exception:  # noqa: BLE001
            pass
        if resp.status_code == 404 or err in ("UNREGISTERED", "NOT_FOUND", "INVALID_ARGUMENT"):
            raise _DeadToken(f"{resp.status_code} {err}")

    resp.raise_for_status()
