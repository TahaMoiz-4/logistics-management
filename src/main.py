"""
src/main.py

FastAPI application entry point.

Run (dev):
    uvicorn src.main:app --reload

The route-plan API lives under /v1/route-plans — create a plan to trigger an
ALNS solve, watch it live over SSE, and read the results + solver diagnostics.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.db.database import check_db_connection
from src.api.v1.auth import router as auth_router
from src.api.v1.route_plans import router as route_plans_router
from src.api.v1.orders import router as orders_router
from src.api.v1.companies import router as companies_router
from src.api.v1.customers import router as customers_router
from src.api.v1.depots import router as depots_router
from src.api.v1.vehicles import router as vehicles_router
from src.api.v1.employees import router as employees_router
from src.api.v1.workers import router as workers_router
from src.api.v1.drivers import router as drivers_router
from src.api.v1.mobile import router as mobile_router
from src.api.v1.tracking import router as tracking_router
from src.api.v1.dashboard import router as dashboard_router
from src.api.v1.meta import router as meta_router
from src.api.v1.geocode import router as geocode_router
from src.api.v1.settings import router as settings_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Warm the caches the routing and geocoding paths depend on.

    Both loads are BEST EFFORT — a failure logs and the app still serves. That
    matters: the graph can take 2-5 minutes to download on a cold machine, and
    letting that block startup would fail health checks and stall deploys.

      * Road graph — previously loaded lazily on the first solve, which meant a
        cold deploy silently charged a multi-minute download to whichever
        dispatcher happened to solve first. Loading it here makes that cost
        visible at boot, and lets /v1/geocode flag unroutable addresses.
        Seed Redis first so this is a fast unpickle:
            docker compose exec backend python -m src.utils.scripts.seed_graph
      * Service-area boundary — the polygon /v1/geocode filters on. Cheap, and
        pre-fetching keeps Nominatim off the first search request.
    """
    from src.services import boundary
    from src.services.maps import load_graph

    try:
        boundary.load_boundary()
        logger.info("Startup: service-area boundary ready (%s)", settings.MAP_PLACE)
    except Exception as e:
        logger.warning(f"Startup: boundary unavailable ({e}); geocode runs unfiltered")

    try:
        G = load_graph()
        logger.info(f"Startup: road graph ready ({G.number_of_nodes():,} nodes)")
    except Exception as e:
        logger.warning(f"Startup: road graph unavailable ({e}); it will load on first solve")

    yield


app = FastAPI(
    title="Logistics Management — ALNS Routing",
    description="Nurse/technician field-service DARP routing engine.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Behind docker compose, nginx serves the console and proxies /v1 to this app,
# so console traffic is same-origin and never triggers CORS. What remains is
# genuinely cross-origin callers: a local Vite dev server on :5173, the mobile
# app, or a console hosted on another domain.
#
# settings.cors_origins_list (src/core/config.py) parses the comma-separated
# CORS_ORIGINS env var into a list, defaulting to the two localhost:5173 forms.
#
# An explicit origin list is what makes allow_credentials=True valid: browsers
# reject Access-Control-Allow-Origin: * on credentialed requests, so the old
# allow_origins=["*"] pairing was permissive-looking and broken at once.
# Methods/headers stay open - an untrusted origin cannot reach the endpoint to
# use them.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(companies_router)
app.include_router(customers_router)
app.include_router(depots_router)
app.include_router(vehicles_router)
app.include_router(employees_router)
app.include_router(workers_router)
app.include_router(drivers_router)
app.include_router(orders_router)
app.include_router(route_plans_router)
app.include_router(mobile_router)
app.include_router(tracking_router)
app.include_router(dashboard_router)
app.include_router(meta_router)
app.include_router(geocode_router)
app.include_router(settings_router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "db": check_db_connection()}


@app.get("/", tags=["health"])
def root():
    return {"service": "logistics-management", "docs": "/docs"}
