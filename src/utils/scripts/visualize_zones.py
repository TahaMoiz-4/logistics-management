"""
scripts/visualize_zones.py

Exports seeded zones to a GeoJSON file you can drag into kepler.gl
to visually verify hex coverage and labels over a Karachi basemap.

Run:
    python -m scripts.visualize_zones

Then:
    1. Go to https://kepler.gl/demo
    2. Drag and drop  assets/karachi_zones.geojson  onto the page
    3. You'll see every hexagon colored by label
"""

import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.database import SessionLocal
from src.db.repositories.zone import ZoneRepository
from src.services.h3_service import h3_boundary_coords

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("assets/karachi_zones.geojson")


def export():
    db   = SessionLocal()
    repo = ZoneRepository(db)

    try:
        zones = repo.get_all_zones(city="Karachi")
        logger.info(f"Exporting {len(zones)} zones...")

        features = []
        for zone in zones:
            # get the 6 corner coordinates of this hexagon
            boundary = h3_boundary_coords(zone.h3_index)

            # GeoJSON wants [lng, lat], h3 gives (lat, lng) — swap them
            coords = [[lng, lat] for lat, lng in boundary]
            # close the polygon ring
            coords.append(coords[0])

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords],
                },
                "properties": {
                    "h3_index":   zone.h3_index,
                    "label":      zone.label,
                    "center_lat": zone.center_lat,
                    "center_lng": zone.center_lng,
                    "city":       zone.city,
                },
            })

        geojson = {
            "type": "FeatureCollection",
            "features": features,
        }

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(geojson, indent=2))
        logger.info(f"✅ Saved to {OUTPUT_PATH}")
        logger.info("→ Drag this file onto https://kepler.gl/demo to visualize")

    finally:
        db.close()


if __name__ == "__main__":
    export()