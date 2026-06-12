"""
scripts/seed_zones.py

One-time setup script: populates the Zone and TrafficProfile tables.

What it does:
  1. Covers Karachi's bounding box with H3 resolution-8 hexagons
  2. Inserts each hex as a Zone row
  3. Generates synthetic TrafficProfile rows per zone based on
     Karachi's known congestion patterns (time-of-day + day type)

Run AFTER alembic upgrade head AND after seed_graph.py:
    python -m scripts.seed_zones

Synthetic multiplier logic (can be tuned later or replaced with learned data):

  Weekday:
    06-08  → 1.2  (early morning, light)
    08-10  → 2.0  (morning rush — DHA, Clifton, Saddar heavy)
    10-12  → 1.3  (mid-morning)
    12-14  → 1.4  (lunch hour)
    14-17  → 1.2  (afternoon)
    17-20  → 1.9  (evening rush)
    20-23  → 1.3  (night)
    23-06  → 1.0  (late night / free flow)

  Friday:
    11-14  → 2.2  (Jumu'ah — significantly worse in Karachi)
    17-20  → 2.0  (Friday evening, everyone heading out)
    others → weekday pattern

  Saturday/Sunday:
    flat 1.2 throughout (lighter traffic)
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import settings
from src.core.enums import DayType, TrafficSource
from src.db.database import SessionLocal
from src.db.repositories.zone import ZoneRepository
from src.services.h3_service import latlng_bbox_to_h3_cells, h3_to_latlng, ZONE_RESOLUTION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Karachi bounding box
# ---------------------------------------------------------------------------

KARACHI_BBOX = dict(
    min_lat=24.74, min_lng=66.85,
    max_lat=25.10, max_lng=67.35,
)

# ---------------------------------------------------------------------------
# Synthetic traffic bands
# Format: (hour_start, hour_end, multiplier)
# hour_end is exclusive  (08-10 means hours 8 and 9, not 10)
# ---------------------------------------------------------------------------

WEEKDAY_BANDS = [
    (0,  6,  1.0),    # late night
    (6,  8,  1.2),    # early morning
    (8,  10, 2.0),    # morning rush
    (10, 12, 1.3),    # mid-morning
    (12, 14, 1.4),    # lunch
    (14, 17, 1.2),    # afternoon
    (17, 20, 1.9),    # evening rush
    (20, 24, 1.3),    # night
]

FRIDAY_BANDS = [
    (0,  6,  1.0),
    (6,  8,  1.2),
    (8,  11, 1.3),
    (11, 14, 2.2),    # Jumu'ah prayer + post-prayer congestion
    (14, 17, 1.4),
    (17, 20, 2.0),    # Friday evening surge
    (20, 24, 1.4),
]

WEEKEND_BANDS = [
    (0,  24, 1.2),    # flat — lighter all day
]

DAY_BANDS = {
    DayType.weekday:        WEEKDAY_BANDS,
    DayType.friday:         FRIDAY_BANDS,
    DayType.saturday:       WEEKEND_BANDS,
    DayType.sunday:         WEEKEND_BANDS,
    DayType.public_holiday: WEEKEND_BANDS,
}


# ---------------------------------------------------------------------------
# Karachi district labels — best-effort from H3 center coords
# We bucket by lat/lng into rough known districts.
# ---------------------------------------------------------------------------

def _guess_label(lat: float, lng: float) -> str:
    """Very rough district bucketing for human-readable zone labels."""
    if lat < 24.82 and lng < 67.05:
        return "Manora / Keamari"
    elif lat < 24.84 and lng < 67.10:
        return "Saddar / Old City"
    elif lat < 24.84 and lng > 67.10:
        return "Korangi / Landhi"
    elif lat < 24.88 and lng < 67.05:
        return "Clifton / DHA"
    elif lat < 24.88 and 67.05 <= lng < 67.15:
        return "Gulshan / PECHS"
    elif lat < 24.88 and lng >= 67.15:
        return "Malir"
    elif lat < 24.94 and lng < 67.05:
        return "North Nazimabad"
    elif lat < 24.94 and lng >= 67.05:
        return "Gulistan-e-Johar / Federal B"
    elif lat >= 24.94 and lng < 67.05:
        return "Orangi / Baldia"
    else:
        return "Surjani / Gadap"


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------

def seed():
    logger.info("=" * 60)
    logger.info("  Karachi Zone + Traffic Profile Seeder")
    logger.info("=" * 60)

    db   = SessionLocal()
    repo = ZoneRepository(db)

    try:
        # ── 1. Generate H3 cells covering Karachi ─────────────────────────
        logger.info("Generating H3 cells for Karachi bounding box...")
        cell_indices = latlng_bbox_to_h3_cells(**KARACHI_BBOX, resolution=ZONE_RESOLUTION)
        logger.info(f"Generated {len(cell_indices):,} H3 cells at resolution {ZONE_RESOLUTION}")

        # ── 2. Build Zone rows ────────────────────────────────────────────
        zone_rows = []
        for idx in cell_indices:
            lat, lng = h3_to_latlng(idx)
            zone_rows.append({
                "h3_index":   idx,
                "resolution": ZONE_RESOLUTION,
                "center_lat": lat,
                "center_lng": lng,
                "city":       "Karachi",
                "label":      _guess_label(lat, lng),
            })

        inserted_zones = repo.bulk_upsert_zones(zone_rows)
        logger.info(f"Zones inserted: {inserted_zones} new  ({len(zone_rows) - inserted_zones} already existed)")

        # ── 3. Build TrafficProfile rows ──────────────────────────────────
        logger.info("Building synthetic traffic profiles...")
        profile_rows = []

        for idx in cell_indices:
            for day_type, bands in DAY_BANDS.items():
                for (h_start, h_end, multiplier) in bands:
                    profile_rows.append({
                        "h3_index":   idx,
                        "day_type":   day_type,
                        "hour_start": h_start,
                        "hour_end":   h_end,
                        "multiplier": multiplier,
                        "road_type":  None,
                        "source":     TrafficSource.synthetic,
                    })

        total_profiles = len(profile_rows)
        logger.info(f"Inserting {total_profiles:,} traffic profiles (this may take a minute)...")

        # Insert in batches to avoid memory pressure
        BATCH = 2000
        total_inserted = 0
        for i in range(0, total_profiles, BATCH):
            batch         = profile_rows[i : i + BATCH]
            inserted      = repo.bulk_insert_profiles(batch)
            total_inserted += inserted
            pct = min(100, int((i + BATCH) / total_profiles * 100))
            logger.info(f"  {pct}%  ({total_inserted:,} new profiles inserted so far)")

        logger.info(f"✅ Traffic profiles: {total_inserted} new inserted")
        logger.info("Seeding complete.")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()