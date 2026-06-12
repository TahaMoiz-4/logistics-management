"""
scripts/seed_graph.py

One-time setup script: downloads the Karachi road network and warms up
both the OSMnx disk cache and the Redis cache.

Run once before starting the app:
    python -m scripts.seed_graph

After this runs:
  - ./cache/          → OSMnx raw HTTP response cache (avoids re-hitting OSM API)
  - Redis             → pickled NetworkX graph (instant load on app startup)

You only need to re-run this if:
  - You want fresher OSM data (road network changes)
  - You wipe your Redis data volume
  - You change GRAPH_CACHE_KEY in maps.py
"""

import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import osmnx as ox
from src.services.maps import (
    GRAPH_CACHE_KEY,
    _load_from_osmnx,
    _save_to_redis,
)

from src.infrastructure.redis.redis import get_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def check_redis() -> bool:
    try:
        r = get_redis()
        r.ping()
        logger.info("✅ Redis connection OK")
        return True
    except Exception as e:
        logger.error(f"❌ Redis not reachable: {e}")
        return False


def seed():
    logger.info("=" * 60)
    logger.info("  Karachi Graph Seeder")
    logger.info("=" * 60)

    # ── 1. Redis check ────────────────────────────────────────────────────
    if not check_redis():
        logger.error("Start Redis (docker compose up -d) and retry.")
        sys.exit(1)

    # ── 2. Check if already cached ────────────────────────────────────────
    r = get_redis()
    if r.exists(GRAPH_CACHE_KEY):
        size = r.memory_usage(GRAPH_CACHE_KEY, samples=0) or 0
        logger.info(
            f"Graph already in Redis cache ({size / 1024 / 1024:.1f} MB). "
            "Pass --force to re-download."
        )
        if "--force" not in sys.argv:
            logger.info("Nothing to do. Exiting.")
            return

    # ── 3. Download / load from OSMnx disk cache ─────────────────────────
    logger.info("Loading Karachi graph via OSMnx...")
    logger.info("(First run downloads from OpenStreetMap — takes 2-5 min)")
    logger.info("(Subsequent runs load from ./cache/ in seconds)")

    t0 = time.time()
    G  = _load_from_osmnx()
    elapsed = time.time() - t0

    nodes = len(G.nodes)
    edges = len(G.edges)
    logger.info(f"Graph loaded in {elapsed:.1f}s  —  {nodes:,} nodes, {edges:,} edges")

    # ── 4. Save to Redis ──────────────────────────────────────────────────
    logger.info("Saving to Redis cache...")
    _save_to_redis(G)

    # ── 5. Verify ─────────────────────────────────────────────────────────
    cached_size = r.memory_usage(GRAPH_CACHE_KEY, samples=0) or 0
    logger.info(f"✅ Graph cached in Redis ({cached_size / 1024 / 1024:.1f} MB)")
    logger.info("App startup will now load the graph from Redis instantly.")


if __name__ == "__main__":
    seed()