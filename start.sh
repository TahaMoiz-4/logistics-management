#!/usr/bin/env bash
#
# start.sh - one-command startup for the Nightingale stack (Linux, GUI desktop).
# Bash equivalent of start.ps1.
#
# In order:
#   0. --bootstrap : create .venv (if missing), pip install deps, npm install frontend.
#   1. Verify Docker is running.
#   2. Ensure postgres + redis containers are up (docker compose up -d if not),
#      wait for healthy.
#   3. alembic upgrade head (idempotent - no-op if already at head).
#   4. --seed : wipe tenant data + re-seed the demo dataset. Otherwise leave data.
#   5. Start backend (uvicorn) in its own terminal window; wait for :8000.
#   6. Start frontend (vite) in its own terminal window.
#
# Usage:
#   ./start.sh                     # start, keep existing DB data
#   ./start.sh --seed              # start + reset & seed demo data
#   ./start.sh --bootstrap --seed  # fresh machine: install deps, then start + seed
#
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

REQUIRED_CONTAINERS=(postgres_db redis_cache)
BACKEND_URL="http://127.0.0.1:8000/openapi.json"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
VENV_PY="$PROJECT_ROOT/.venv/bin/python"

SEED=false
BOOTSTRAP=false
for arg in "$@"; do
    case "$arg" in
        --seed) SEED=true ;;
        --bootstrap) BOOTSTRAP=true ;;
        *) echo "Unknown arg: $arg (valid: --seed, --bootstrap)"; exit 1 ;;
    esac
done

# colors (fall back to plain if not a tty)
if [ -t 1 ]; then C='\033[36m'; G='\033[32m'; R='\033[31m'; Z='\033[0m'; else C=''; G=''; R=''; Z=''; fi
step() { echo -e "\n${C}==> $1${Z}"; }
ok()   { echo -e "    ${G}OK  $1${Z}"; }
err()  { echo -e "    ${R}ERR $1${Z}"; }

# Prefer venv python, else system python3.
PY="python3"
[ -x "$VENV_PY" ] && PY="$VENV_PY"

# Pick a terminal emulator for launching a service in its own window.
# Echoes a function name to call; empty if none found.
pick_terminal() {
    for t in gnome-terminal konsole xfce4-terminal xterm; do
        command -v "$t" >/dev/null 2>&1 && { echo "$t"; return; }
    done
    echo ""
}

# launch_window <title> <shell-command>
# Opens the command in a new terminal window if one is available; otherwise
# falls back to a background process logging to <title>.log.
launch_window() {
    local title="$1" cmd="$2" term
    term="$(pick_terminal)"
    case "$term" in
        gnome-terminal)  gnome-terminal --title="$title" -- bash -lc "$cmd; exec bash" & ;;
        konsole)         konsole -p tabtitle="$title" -e bash -lc "$cmd; exec bash" & ;;
        xfce4-terminal)  xfce4-terminal --title="$title" -x bash -lc "$cmd; exec bash" & ;;
        xterm)           xterm -T "$title" -e bash -lc "$cmd; exec bash" & ;;
        "")
            local log="$PROJECT_ROOT/${title}.log"
            echo "    (no terminal emulator found - running '$title' in background -> $log)"
            nohup bash -lc "$cmd" > "$log" 2>&1 &
            echo "    $title PID $!"
            ;;
    esac
}

# -- 0. Bootstrap -------------------------------------------------------------
if $BOOTSTRAP; then
    step "Bootstrapping dependencies (--bootstrap given)"
    if [ ! -x "$VENV_PY" ]; then
        echo "    Creating virtualenv at .venv"
        python3 -m venv "$PROJECT_ROOT/.venv" || { err "python3 -m venv failed (is python3 installed?)."; exit 1; }
    else
        echo "    .venv already exists - reusing it"
    fi
    PY="$VENV_PY"
    echo "    Installing Python deps (pip install -r requirements.txt)"
    "$PY" -m pip install --upgrade pip >/dev/null
    "$PY" -m pip install -r "$PROJECT_ROOT/requirements.txt" || { err "pip install failed."; exit 1; }
    echo "    Installing frontend deps (npm install)"
    ( cd "$FRONTEND_DIR" && npm install ) || { err "npm install failed (is Node installed?)."; exit 1; }
    ok "Bootstrap complete"
fi
# re-resolve python in case bootstrap just created the venv
[ -x "$VENV_PY" ] && PY="$VENV_PY"

# -- 1. Docker daemon ---------------------------------------------------------
step "Checking Docker is running"
if ! docker info >/dev/null 2>&1; then
    err "Docker is not running. Start Docker (or the daemon) and re-run this script."
    exit 1
fi
ok "Docker daemon is up"

# -- 2. Containers ------------------------------------------------------------
step "Checking required containers: ${REQUIRED_CONTAINERS[*]}"
running="$(docker ps --format '{{.Names}}')"
missing=()
for name in "${REQUIRED_CONTAINERS[@]}"; do
    echo "$running" | grep -qx "$name" || missing+=("$name")
done
if [ "${#missing[@]}" -gt 0 ]; then
    echo "    Missing: ${missing[*]} - bringing them up with docker compose"
    docker compose up -d || { err "docker compose up failed."; exit 1; }
fi

echo "    Waiting for containers to become healthy..."
for name in "${REQUIRED_CONTAINERS[@]}"; do
    healthy=false
    for _ in $(seq 1 30); do
        status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name" 2>/dev/null || echo missing)"
        if [ "$status" = "healthy" ] || [ "$status" = "none" ]; then healthy=true; break; fi
        sleep 1
    done
    if $healthy; then ok "$name ready"; else err "$name did not become healthy in time."; exit 1; fi
done

# -- 3. Alembic (idempotent) --------------------------------------------------
step "Applying database migrations (alembic upgrade head)"
"$PY" -m alembic upgrade head || { err "alembic upgrade head failed."; exit 1; }
ok "Database is at head (no-op if it already was)"

# -- 4. Optional demo seed ----------------------------------------------------
if $SEED; then
    step "Seeding demo data (--seed given): reset + seed"
    "$PY" -m src.utils.scripts.reset_tenant_data --yes || { err "reset failed."; exit 1; }
    "$PY" -m src.utils.scripts.seed_demo_dataset || { err "seed failed."; exit 1; }
    ok "Demo dataset seeded (admin1/admin2, worker1.. all password 'password')"
else
    step "Skipping seed (pass --seed to reset + load demo data)"
fi

# -- 5. Backend in its own window, then wait ---------------------------------
step "Starting backend (uvicorn) in a new window"
launch_window "backend" "cd '$PROJECT_ROOT' && '$PY' -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload"

echo "    Waiting for backend on :8000..."
backend_up=false
for _ in $(seq 1 40); do
    if curl -s -o /dev/null --max-time 2 "$BACKEND_URL"; then backend_up=true; break; fi
    sleep 1
done
if $backend_up; then ok "Backend is up at http://127.0.0.1:8000"; else err "Backend did not come up in time - check its window/log."; exit 1; fi

# -- 6. Frontend in its own window -------------------------------------------
step "Starting frontend (vite) in a new window"
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "    node_modules missing - running npm install first"
    ( cd "$FRONTEND_DIR" && npm install )
fi
launch_window "frontend" "cd '$FRONTEND_DIR' && npm run dev"
ok "Frontend starting (usually http://localhost:5173)"

echo -e "\n${C}==> Stack is up.${Z}"
echo "    Backend : http://127.0.0.1:8000  (docs at /docs)"
echo "    Frontend: http://localhost:5173"
echo "    Web login   : admin1 (nurse co) / admin2 (tech co) - password 'password'"
echo "    Mobile login: worker1.. - password 'password'"
echo "    Fresh machine? run once: ./start.sh --bootstrap --seed"
