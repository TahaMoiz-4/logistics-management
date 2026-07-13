"""src/db/repositories/device_token.py — FCM device token registration + lookup."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import DeviceToken
from src.core.enums import DevicePlatform


class DeviceTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def register(self, employee_id: int, token: str,
                 platform: DevicePlatform = DevicePlatform.android) -> DeviceToken:
        """Upsert a device token for a worker. Reactivates + touches an existing one."""
        existing = (
            self.db.query(DeviceToken)
            .filter(DeviceToken.token == token, DeviceToken.deleted_at.is_(None))
            .first()
        )
        now = datetime.now(timezone.utc)
        if existing:
            existing.employee_id = employee_id
            existing.platform = platform
            existing.active = True
            existing.last_seen = now
            self.db.commit()
            self.db.refresh(existing)
            return existing
        dt = DeviceToken(employee_id=employee_id, token=token, platform=platform,
                        active=True, last_seen=now, created_by=employee_id)
        self.db.add(dt)
        self.db.commit()
        self.db.refresh(dt)
        return dt

    def active_tokens_for(self, employee_id: int) -> list[str]:
        rows = (
            self.db.query(DeviceToken)
            .filter(DeviceToken.employee_id == employee_id,
                    DeviceToken.active.is_(True), DeviceToken.deleted_at.is_(None))
            .all()
        )
        return [r.token for r in rows]

    def deactivate(self, token: str) -> None:
        row = self.db.query(DeviceToken).filter(DeviceToken.token == token).first()
        if row:
            row.active = False
            self.db.commit()
