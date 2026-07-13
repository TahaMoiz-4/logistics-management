"""
src/main.py

FastAPI application entry point.

Run (dev):
    uvicorn src.main:app --reload

The route-plan API lives under /v1/route-plans — create a plan to trigger an
ALNS solve, watch it live over SSE, and read the results + solver diagnostics.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Logistics Management — ALNS Routing",
    description="Nurse/technician field-service DARP routing engine.",
    version="0.1.0",
)

# CORS wide-open for the demo frontend (tighten for production).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "db": check_db_connection()}


@app.get("/", tags=["health"])
def root():
    return {"service": "logistics-management", "docs": "/docs"}
