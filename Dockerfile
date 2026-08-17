# syntax=docker/dockerfile:1
#
# Nightingale backend (FastAPI + ALNS solver).
#
# Multi-stage: dependencies are installed in `builder` with a compiler present,
# then only the finished site-packages tree is copied into `runtime`. The
# compiler, headers and pip caches never reach the shipped image.
#
# Build:  docker compose build backend
# Run:    docker compose up -d          (see docker-compose.yaml)

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: builder
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

# Debian slim (not Alpine) on purpose: geopandas / pyproj / shapely / scipy /
# scikit-learn publish manylinux wheels that install as prebuilt binaries here.
# Alpine uses musl libc, which those wheels don't target, so pip would fall back
# to compiling PROJ/GEOS/BLAS from source - a ~20 minute build that often fails.
#
# build-essential + libpq-dev cover the few packages without a matching wheel
# (and psycopg2's headers). They stay in this stage only.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Dependencies BEFORE source. Docker caches each layer against its inputs, so as
# long as requirements.txt is unchanged this whole install - all 50+ packages,
# scipy and geopandas included - is reused. Copying source first would bust the
# cache on every code edit and re-download everything on each redeploy.
COPY requirements.txt .

# --prefix collects everything into one tree that the runtime stage can copy in
# a single COPY. No --user: that writes to /root, which the non-root app user
# in the runtime stage could not read.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# libpq5 is the Postgres client *runtime* library (libpq-dev's headers were only
# needed to build). GDAL/GEOS/PROJ system packages are deliberately absent:
# pyogrio, shapely and pyproj bundle their own native libs inside their wheels.
#
# curl is here for the container healthcheck below.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# PYTHONUNBUFFERED: send logs straight to Docker instead of sitting in a buffer,
# so `docker compose logs -f backend` is live rather than stuttering.
# PYTHONDONTWRITEBYTECODE: no .pyc litter in a read-only-ish container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH=/usr/local/bin:$PATH

# The installed dependency tree from the builder stage.
COPY --from=builder /install /usr/local

WORKDIR /app

# Run as a non-root user: if the app is ever compromised, the attacker lands as
# an unprivileged account rather than root inside the container.
RUN useradd --create-home --uid 1000 app

# Only what the app actually needs at runtime. Note src/secrets/ and .env are
# excluded by .dockerignore and supplied at runtime instead.
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic/ ./alembic/
COPY --chown=app:app src/ ./src/
COPY --chown=app:app assets/ ./assets/
COPY --chown=app:app docker-entrypoint.sh ./

# These are bind-mounted from the host in docker-compose.yaml. Creating them
# owned by `app` means the mounts land on writable directories - without this,
# OSMnx's cache writes (src/services/maps.py sets cache_folder="./cache") would
# hit a permission error as the non-root user.
RUN mkdir -p /app/cache /app/logs /app/map_cache \
    && chown -R app:app /app/cache /app/logs /app/map_cache \
    && chmod +x /app/docker-entrypoint.sh

USER app

EXPOSE 8000

# Compose uses this to gate the frontend's startup on a genuinely-ready backend.
# /openapi.json is the same readiness probe start.sh polls.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/openapi.json || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
