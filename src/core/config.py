from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Postgres ──────────────────────────────────────────────────────────
    # Full DSN, e.g.:
    #   postgresql://logistics_user:yourpassword@localhost:5432/logistics_db
    DATABASE_URL: str

    # Set to True in .env during development to print every SQL query
    DB_ECHO: bool = False

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Firebase Cloud Messaging (push notifications) ─────────────────────
    # When BOTH are set, src/services/notifications/fcm.py sends real FCM HTTP
    # v1 pushes; otherwise it runs in STUB mode (logs intent, sends nothing).
    # Set these in .env once the Firebase project + service-account JSON exist.
    FIREBASE_CREDENTIALS_PATH: str = ""    # path to the service-account JSON
    FIREBASE_PROJECT_ID: str = ""          # Firebase project id

    # ── App ───────────────────────────────────────────────────────────────
    APP_ENV: str = "development"   # development | production
    SECRET_KEY: str = "change-me-in-production"
    
    # ── Matrix builder ─────────────────────────────────────────────────────
    # Returned for unreachable pairs — large enough that OR-Tools avoids them
    # but not so large it breaks the solver's integer arithmetic
    PENALTY_SEC: int = 7 * 3600          # 7 hours

    # Redis TTL for cached pairs — 24 hours
    CACHE_TTL_SEC: int = 86_400

    # ── Fuel prices ────────────────────────────────────────────────────────
    # PKR per litre (petrol/diesel/cng) or per kWh (electric). Used by the
    # ALNS FuelCost component: distance_km * vehicle.fuel_average * price.
    # Keyed by FuelType enum values. Editable per deployment; can be overridden
    # per run via RoutePlan.optimization_params if needed later.
    FUEL_PRICES: dict[str, float] = {
        "petrol":   280.0,
        "diesel":   290.0,
        "cng":      190.0,
        "electric":  60.0,
    }

    # ── ALNS defaults ──────────────────────────────────────────────────────
    # Fallback service duration (minutes) when Order.service_duration_min is null
    DEFAULT_SERVICE_DURATION_MIN: int = 30

    # Penalty weights + thresholds for the objective function. Every value here
    # is a DEFAULT — a solve can override any of them via
    # RoutePlan.optimization_params. See src/services/alns/cost.py.
    ALNS_PENALTIES: dict[str, float] = {
        # per-order lateness beyond its time window, per minute
        "tardiness_per_min":        2.0,
        # per-worker shift overrun, per minute
        "overtime_per_min":         3.0,
        # a worker assigned an order they lack the skill for (safety net;
        # should be near-impossible since insertion is skill-hard-filtered)
        "skill_violation":        200.0,
        # per order left unassigned
        "unserved_order":         500.0,
        # worker waiting on driver pickup, per minute BEYOND the free threshold
        "excess_wait_per_min":      5.0,
        # flat penalty when a dropoff/pickup can't be feasibly served within
        # SHUTTLE_INFEASIBLE_AFTER_MIN by the nearest driver (Section 4/9)
        "shuttle_infeasible":     300.0,
    }

    # Free wait a worker may incur before ExcessWaitCost kicks in (minutes)
    EXCESS_WAIT_THRESHOLD_MIN: int = 15
    # Past this pickup/dropoff delay, ShuttleInfeasibilityCost also fires (minutes)
    SHUTTLE_INFEASIBLE_AFTER_MIN: int = 45

    # ── Ride-sharing / multi-rider batching (DARP pooling) ─────────────────
    # Workers heading to orders in the SAME H3 zone within POOL_WINDOW_MIN of
    # each other can share one driver leg, up to the vehicle's seating_capacity.
    # This is what makes the shuttle a true dial-a-ride rather than one trip per
    # worker. All tunable.
    POOL_ENABLED: bool = True
    POOL_WINDOW_MIN: int = 60          # riders within this many minutes can pool
    POOL_H3_RESOLUTION: int = 8        # res-8 (~460m neighbourhood) = "same area"

    # ── Live tracking ──────────────────────────────────────────────────────
    # A worker/vehicle position older than this is considered STALE (the map
    # greys it out). Positions older than TRACKING_DROP_MIN are omitted entirely.
    TRACKING_STALE_AFTER_SEC: int = 15 * 60      # 15 min -> stale
    TRACKING_DROP_AFTER_MIN: int = 24 * 60       # 24 h  -> not returned at all

    # ALNS loop defaults (overridable per-run via optimization_params.alns_config)
    ALNS_CONFIG: dict = {
        "max_runtime_sec": 60,
        "seed":            42,
        "sa_start_temp":   100.0,
        "sa_end_temp":     1.0,
        "sa_step":         0.9995,
        "destroy_pct_range": [0.1, 0.3],
    }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()