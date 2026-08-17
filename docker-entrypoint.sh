#!/usr/bin/env bash
#
# docker-entrypoint.sh - what the backend container does on every start.
#
# Mirrors steps 3 and 5 of start.sh, minus the laptop assumptions (no venv, no
# terminal windows, no waiting on Docker - compose's depends_on already gated us
# on postgres and redis being healthy).
#
# Seeding is deliberately NOT here. seed_demo_dataset calls reset_tenant_data,
# which wipes tenant rows; a container restart at 3am must never do that to a
# client demo. Seed once, by hand:
#
#   docker compose exec backend python -m src.utils.scripts.seed_demo_dataset
#
set -euo pipefail

echo "==> Applying database migrations (alembic upgrade head)"
alembic upgrade head
echo "    OK  database is at head"

echo "==> Starting uvicorn on 0.0.0.0:8000"

# Two things worth noting about this line:
#
#  --host 0.0.0.0, not 127.0.0.1. Inside a container 127.0.0.1 means "this
#    container only", so nginx on the app-network could never reach it. 0.0.0.0
#    binds all interfaces. That is not an exposure risk here: the backend
#    publishes no host port, so the only route in is through nginx.
#
#  exec. Replaces this shell with uvicorn so uvicorn becomes PID 1 and receives
#    Docker's SIGTERM directly. Without exec, the shell holds PID 1, ignores the
#    signal, and every `docker compose down` waits the full 10s timeout before
#    the container is killed - dropping in-flight SSE streams uncleanly.
#
#  ONE worker, deliberately. src/api/v1/progress.py bridges a running solve to
#    its SSE stream through an in-process dict, and says so: "Not multi-worker
#    safe by design (would need Redis pub/sub)". With 2 workers the POST that
#    starts a solve and the GET that streams it can land on different processes,
#    and the stream 404s with "no active solve" - intermittently, since it
#    depends which worker gets the request.
#
#    Raising UVICORN_WORKERS is safe only after progress.py moves to Redis
#    pub/sub. Until then this is the ceiling, not a tuning knob.
exec uvicorn src.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-1}" \
    --proxy-headers \
    --forwarded-allow-ips '*'
