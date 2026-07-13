"""src/db/repositories/worker_position.py — worker GPS ingest + latest-position reads."""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import WorkerPositionEvent
from src.core.enums import ServiceType, PositionSource


class WorkerPositionRepository:
    def __init__(self, db: Session):
        self.db = db

    def record_batch(self, worker_id: int, worker_type: ServiceType,
                     pings: list[dict], source: PositionSource = PositionSource.gps) -> int:
        """
        Insert a batch of GPS pings. Each ping: {lat, lng, recorded_at(optional),
        accuracy_m(optional)}. Returns count inserted.
        """
        from src.services.h3_service import latlng_to_h3
        n = 0
        for p in pings:
            lat, lng = float(p["lat"]), float(p["lng"])
            self.db.add(WorkerPositionEvent(
                worker_id=worker_id, worker_type=worker_type,
                lat=lat, lng=lng, h3_index=latlng_to_h3(lat, lng),
                accuracy_m=p.get("accuracy_m"),
                recorded_at=p.get("recorded_at") or datetime.utcnow(),
                source=source,
            ))
            n += 1
        self.db.commit()
        return n

    def latest_for_worker(self, worker_id: int, worker_type: ServiceType) -> Optional[WorkerPositionEvent]:
        return (
            self.db.query(WorkerPositionEvent)
            .filter(WorkerPositionEvent.worker_id == worker_id,
                    WorkerPositionEvent.worker_type == worker_type)
            .order_by(WorkerPositionEvent.recorded_at.desc())
            .first()
        )
