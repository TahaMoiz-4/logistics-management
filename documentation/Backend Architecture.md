# Nightingale — Backend Architecture & Flow

> A deep tour of the Nightingale backend: how it's layered, how a request travels
> through it, and — in the most detail — how the **ALNS routing engine** turns a pile of
> orders into a solved, dispatchable plan. Written so an engineer new to the codebase can
> read this once and know where everything lives and why it works the way it does.
>
> The backend is a **FastAPI** application ([src/main.py](../src/main.py)) over **PostgreSQL**
> (SQLAlchemy ORM), with **Redis** for travel-time caching and **OSMnx** road-graph routing.
> The optimizer is a custom Adaptive Large Neighborhood Search (ALNS) solver.

---

## Table of Contents

1. [System at a Glance](#1-system-at-a-glance)
2. [Layered Architecture](#2-layered-architecture)
   - 2.1 [The Layers](#21-the-layers)
   - 2.2 [Directory Map](#22-directory-map)
3. [Request Lifecycle](#3-request-lifecycle)
4. [Authentication & Multi-Tenancy](#4-authentication--multi-tenancy)
   - 4.1 [Two Identities](#41-two-identities)
   - 4.2 [The Token](#42-the-token)
   - 4.3 [Tenant Isolation](#43-tenant-isolation)
5. [The Repository Layer](#5-the-repository-layer)
6. [The Routing Stack (Roads, Traffic, Matrices)](#6-the-routing-stack-roads-traffic-matrices)
7. [The ALNS Optimization Engine](#7-the-alns-optimization-engine)
   - 7.1 [The Core Idea: Worker-Centric, Driver-Derived](#71-the-core-idea-worker-centric-driver-derived)
   - 7.2 [The Solve Pipeline](#72-the-solve-pipeline)
   - 7.3 [ProblemData — the Immutable Instance](#73-problemdata--the-immutable-instance)
   - 7.4 [RoutingState & the Derive Pass](#74-routingstate--the-derive-pass)
   - 7.5 [The Cost Function](#75-the-cost-function)
   - 7.6 [Destroy & Repair Operators](#76-destroy--repair-operators)
   - 7.7 [The ALNS Loop](#77-the-alns-loop)
   - 7.8 [Persistence & Diagnostics](#78-persistence--diagnostics)
8. [End-to-End: Create a Plan → Dispatch](#8-end-to-end-create-a-plan--dispatch)
   - 8.1 [Live Progress over SSE](#81-live-progress-over-sse)
   - 8.2 [Approval & Notifications](#82-approval--notifications)
9. [The Mobile Flow](#9-the-mobile-flow)
10. [Live Tracking](#10-live-tracking)
11. [Cross-Cutting Concerns](#11-cross-cutting-concerns)
12. [Known Design Limits](#12-known-design-limits)

---

## 1. System at a Glance

```
                        ┌──────────────────┐        ┌──────────────────┐
                        │  Web Admin (SPA) │        │  Mobile App      │
                        │  dispatchers     │        │  field workers   │
                        └────────┬─────────┘        └────────┬─────────┘
                                 │  Bearer token             │  Bearer token
                                 │  (SysUser)                │  (Employee)
                                 ▼                           ▼
                        ┌───────────────────────────────────────────────┐
                        │                FastAPI  (src/main.py)          │
                        │   auth · orders · route-plans · mobile ·       │
                        │   tracking · dashboard · CRUD routers          │
                        └───────┬───────────────────────┬────────────────┘
                                │                        │
                 ┌──────────────▼─────────┐   ┌──────────▼───────────────┐
                 │  Services              │   │  Repositories            │
                 │  ALNS solver, routing, │   │  company-scoped, soft-   │
                 │  matrix, maps, FCM     │   │  deleting CRUD           │
                 └───┬──────────┬─────────┘   └──────────┬───────────────┘
                     │          │                        │
             ┌───────▼──┐  ┌────▼─────┐          ┌───────▼────────┐
             │  OSMnx   │  │  Redis   │          │  PostgreSQL    │
             │ road net │  │  matrix  │          │  (SQLAlchemy)  │
             │          │  │  cache   │          │                │
             └──────────┘  └──────────┘          └────────────────┘
```

The backend serves **two clients** with **two separate identities**, exposes a **REST + SSE**
API, and leans on three infrastructure dependencies: PostgreSQL (system of record), Redis
(travel-time cache), and an OSMnx road-network graph (real drive times + geometry).

---

## 2. Layered Architecture

### 2.1 The Layers

The backend follows a conventional layered design. Data flows **down** on the way in and
**up** on the way out; each layer only talks to the one directly beneath it.

```
   HTTP request
        │
        ▼
┌───────────────────┐   FastAPI routers. Parse/validate input (Pydantic schemas),
│  API  (api/v1)    │   enforce auth via dependencies, shape responses. Thin — no
│                   │   business logic beyond orchestration.
└─────────┬─────────┘
          ▼
┌───────────────────┐   The brains: ALNS solver, road routing, matrix building,
│  Services         │   notifications. Pure logic; takes a DB session but owns the
│  (services/)      │   "how".
└─────────┬─────────┘
          ▼
┌───────────────────┐   Company-scoped, soft-deleting CRUD over the ORM. The only
│  Repositories     │   place raw queries *should* live (some services still query
│  (db/repositories)│   directly — a known cleanup item).
└─────────┬─────────┘
          ▼
┌───────────────────┐   SQLAlchemy models = the tables. See DATA_AND_CONFIG_REFERENCE.md
│  Models (db/models)│  for the full column-by-column breakdown.
└─────────┬─────────┘
          ▼
     PostgreSQL
```

Supporting modules sit alongside these layers:

- **`core/`** — configuration ([config.py](../src/core/config.py)), enums
  ([enums.py](../src/core/enums.py)), and security primitives ([security.py](../src/core/security.py)).
- **`schemas/`** — Pydantic request/response models (the API contract, separate from the ORM).
- **`exceptions/`** — typed domain exceptions grouped by area (auth, orders, route_plans, …).
- **`infrastructure/`** — Redis client + cache helpers.

### 2.2 Directory Map

```
src/
├── main.py                 FastAPI app; mounts every router; /health
├── api/v1/                 HTTP layer (one router per resource)
│   ├── deps.py             auth dependencies (get_current_user / get_current_worker)
│   ├── auth.py             web login/logout/me
│   ├── mobile.py           the entire Flutter-app API surface
│   ├── route_plans.py      create solve + SSE + results + approve
│   ├── progress.py         in-process SSE channel registry
│   ├── orders.py           order CRUD + "servable" picker
│   ├── tracking.py         live positions + availability roster
│   ├── dashboard.py        aggregate stats
│   └── companies/customers/depots/vehicles/employees/workers/drivers/meta.py
├── core/                   config, enums, security
├── db/
│   ├── database.py         engine, SessionLocal, get_db dependency
│   ├── models/             SQLAlchemy tables
│   └── repositories/       company-scoped CRUD (BaseRepository + per-entity)
├── services/
│   ├── alns/               the optimizer (see §7)
│   ├── routing.py          single origin→dest road route (traffic-adjusted)
│   ├── matrix.py           N×N travel-time matrix (Redis-cached)
│   ├── maps.py             OSMnx graph load + traffic application
│   ├── h3_service.py       lat/lng ↔ H3 helpers
│   └── notifications/fcm.py push notifications (stub or real FCM)
├── schemas/                Pydantic request/response contracts
├── exceptions/             typed domain errors
└── infrastructure/redis/   Redis client + cache key helpers
```

---

## 3. Request Lifecycle

Every authenticated request follows the same skeleton. FastAPI's dependency injection wires
the pieces together automatically.

```
1. Request arrives            POST /v1/route-plans   Authorization: Bearer <token>
        │
2. CORS middleware            (wide-open for the demo — main.py)
        │
3. Dependency resolution      get_db()          → yields a per-request DB session
        │                     get_current_user()→ verifies token, loads SysUser,
        │                                          pins company_id from the token
        │
4. Pydantic validation        request body → CreateRoutePlanRequest (rejects bad input)
        │
5. Handler runs               orchestrates services/repositories
        │
6. Response serialization     return value → response_model → JSON
        │
7. Teardown                   get_db()'s finally: closes the session
```

The DB session is **request-scoped**: [get_db()](../src/db/database.py) yields one
`SessionLocal` and guarantees it's closed when the request ends, even on error. The engine
uses a connection pool (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`) so a dropped
Postgres connection is transparently re-established.

---

## 4. Authentication & Multi-Tenancy

Auth is deliberately small — no JWT library, no session store — but it is the backbone of
tenant isolation. It lives in [core/security.py](../src/core/security.py) (primitives) and
[api/v1/deps.py](../src/api/v1/deps.py) (dependencies).

### 4.1 Two Identities

There are **two kinds of caller**, authenticated separately and never interchangeable:

| Identity        | Who                     | Logs in via                    | Dependency            | Table       |
|-----------------|-------------------------|--------------------------------|-----------------------|-------------|
| **CurrentUser** | Web operator / admin    | `POST /v1/auth/login`          | `get_current_user`    | `sys_users` |
| **CurrentWorker** | Mobile field worker   | `POST /v1/mobile/auth/login`   | `get_current_worker`  | `employees` |

The token embeds a **subject type** (`sysuser` vs `employee`); each dependency refuses a token
of the wrong type, so a worker token can never reach a web-only endpoint and vice versa.

### 4.2 The Token

A minimal, HMAC-signed token — stdlib only, no JWT dependency:

```
token = base64url(payload) . base64url( HMAC_SHA256(payload, SECRET_KEY) )

payload = { "sub": <subject id>, "typ": "sysuser"|"employee",
            "cid": <company id>, "iat": <issued-at> }
```

The server is **stateless**: it re-verifies the signature on every request with a constant-time
compare. There's no server-side token store and (a documented gap) **no expiry yet** — logout is
purely the client dropping the token.

### 4.3 Tenant Isolation

This is the single most important invariant in the backend:

> **`company_id` always comes from the verified token (`cid`), never from the request body or
> query string.**

Because of this, an endpoint physically cannot be tricked into acting on another company's data
by a forged parameter. The route-plan creation flow, for example, takes `company_id` from
`current.company_id` and *derives* the planned date from the selected orders — the client never
supplies the tenant. The repository layer reinforces this a second time (§5).

---

## 5. The Repository Layer

All entity CRUD is meant to go through repositories in
[db/repositories/](../src/db/repositories/). The generic
[BaseRepository](../src/db/repositories/base.py) gives every entity three guarantees for free:

- **Company scoping** — every `get`/`list` filters `company_id == <caller's company>`, so a
  repo can never return another tenant's rows.
- **Soft delete** — every read filters `deleted_at IS NULL`; deletes stamp `deleted_at` /
  `deleted_by` instead of removing rows.
- **Audit stamping** — creates/updates stamp `created_by` / `updated_by` from the acting user.

```
BaseRepository (generic)
   _base_query(company_id)  →  filter(deleted_at IS NULL) [+ company_id]
   get / list               →  scoped reads
   create / update          →  stamp actor, commit, refresh
   soft_delete              →  set deleted_at/by, commit

   subclassed by: OrderRepository, EmployeeRepository, VehicleRepository, …
                  (each sets `model = <ORM class>`)
```

> **Note:** some services still issue raw ORM queries directly rather than going through a
> repository — a known consistency cleanup tracked in the future-improvements doc.

---

## 6. The Routing Stack (Roads, Traffic, Matrices)

Before the optimizer can reason about "how long from A to B," it needs real drive times. Three
service modules provide them, from lowest-level to highest:

```
maps.py        load_graph()               → the OSMnx road network (MultiDiGraph)
   │           apply_traffic_to_graph(G,m) → scale edge travel_time by multiplier m
   │           get_nearest_node / route_to_geojson
   ▼
routing.py     route_between(A, B, when)   → shortest path by travel_time, traffic-adjusted
   │           get_multiplier_for_location → lat/lng → H3 res-9 → res-8 zone →
   │                                          TrafficProfile lookup (default 1.0)
   ▼
matrix.py      build_matrix(locations)     → N×N travel-time matrix, Redis-cached per pair
```

**How traffic enters the picture.** A location's coordinates are converted to an H3 res-9 hex,
then to its res-8 parent "zone." That zone + the day-type + the hour is looked up in the
`traffic_profiles` table to get a **multiplier** (e.g. `1.4` = 40 % slower). The multiplier
scales the free-flow travel time of the road graph. No profile found ⇒ free-flow `1.0`.

**Caching.** Matrix pairs are cached in Redis, keyed on rounded coordinates + day-type + hour
(see [redis.py](../src/infrastructure/redis/redis.py) `_cache_key`), with a 24 h TTL. Cache
misses route through OSMnx once, then store the result. Unreachable pairs get a large penalty
time (`PENALTY_SEC`) instead of failing the whole matrix.

> The ALNS solver does **not** call this stack in its inner loop. Instead it front-loads all
> travel times into an immutable per-hour matrix once (§7.3), then reads from memory — routing
> the road graph inside a tight search loop would be far too slow.

---

## 7. The ALNS Optimization Engine

This is the heart of the system. It lives in [services/alns/](../src/services/alns/) and turns
a company's orders for one day into an optimized, dispatchable route plan.

### 7.1 The Core Idea: Worker-Centric, Driver-Derived

The domain is a **hybrid Dial-A-Ride Problem (DARP)**. Two distinct actors:

- **Workers** (nurses/technicians) *serve* orders — but they **don't drive**.
- **Drivers** (with vehicles) *shuttle* workers between order locations.

The key architectural decision that makes this tractable:

> **The search only ever manipulates per-worker order sequences. The entire driver-shuttle
> schedule is *derived* from those sequences, not searched.**

```
   WHAT THE SEARCH MUTATES              WHAT IS DERIVED (deterministic)
   ┌──────────────────────────┐        ┌────────────────────────────────────┐
   │ worker_routes:           │        │ derive_driver_routes():            │
   │   nurse#3 → [O7, O2, O9]  │  ───►  │  for each move a worker needs,     │
   │   nurse#5 → [O1, O4]      │        │  assign the nearest feasible       │
   │ unassigned → [O8]         │        │  driver+vehicle; pool riders;      │
   └──────────────────────────┘        │  compute timings + delays          │
                                        └────────────────────────────────────┘
```

This keeps the search space small and the operators simple (they just move order IDs between
lists), while the derive pass guarantees the two layers never silently drift — every worker
sequence is always priced against whether real drivers could actually deliver it.

### 7.2 The Solve Pipeline

A solve is orchestrated by [runner.py](../src/services/alns/runner.py)'s `run_solve()`, which
runs in a **background thread** (FastAPI `BackgroundTasks`). It never crashes the process —
any failure is caught and recorded as a `failed` plan.

```
run_solve(plan_id, company_id, date, …)
   │
   ├─ 1. status = optimizing;  publish "loading"
   │
   ├─ 2. pick TravelTimeProvider
   │        OSMnx (real roads)  ──default──►  if graph won't load (INFRA failure only)
   │                                          fall back to Haversine straight-line + warn
   │
   ├─ 3. load_problem_data(db, company, date, provider)   → immutable ProblemData
   │        publish "solving" {orders, workers, drivers, vehicles}
   │
   ├─ 4. solve(pd, …, progress_cb=publish)                → SolveResult (best state)
   │        streams "best"/"progress" events during the loop
   │
   ├─ 5. persist_solution(db, plan, best, result)         → writes rows + diagnostics
   │        publish "persisting"
   │
   └─ 6. finish("done" {objective, improvement, iterations, unserved})
         ── on any exception ──► status = failed; finish("error" {error_code, message})
```

`run_solve` is intentionally free of any FastAPI types — it takes plain `publish`/`finish`
callables — so it is unit-testable headless.

### 7.3 ProblemData — the Immutable Instance

[problem_data.py](../src/services/alns/problem_data.py) loads one **single-company, single-day**
instance into an immutable, in-memory `ProblemData`. Once built, it is **shared read-only** across
the whole search — never copied per iteration.

**What it contains:**

- **`nodes`** — index 0 is the **depot**, then one node per order location. All matrices are
  indexed by these node positions.
- **`orders` / `workers` / `vehicles` / `drivers`** — lightweight frozen value types
  (`OrderInfo`, `WorkerInfo`, …), stripped of ORM identity so they're safe to share.
- **`travel_time_sec[hour][i][j]`** — a **per-hour travel-time stack**. Distances are
  traffic-independent (computed once); travel times are the free-flow time scaled by each
  hour's traffic multiplier. This bakes time-of-day traffic into memory so the objective never
  touches OSMnx.
- **Feasibility helpers** — `worker_can_serve(w, o)` (skill hard-filter),
  `driver_can_drive(d, v)` (vehicle-type eligibility).

**Order selection is single-day by construction:** only `pending`/`assigned` orders with a
`location_id` whose `service_date` equals the planned date are loaded. Only **active** workers
are eligible (a self-unavailable worker is skipped for new plans).

**Pluggable travel-time providers** let the same shape serve two worlds:

| Provider           | Distance         | Use case                                        |
|--------------------|------------------|-------------------------------------------------|
| `OSMnxProvider`    | real road paths  | production/DB solves; routes each pair once, caches geometry for persistence. Hard-fails `LocationUnroutable` on genuinely un-routable data. |
| `HaversineProvider`| great-circle     | synthetic instances, unit tests, and **infra-failure fallback** only |

### 7.4 RoutingState & the Derive Pass

[state.py](../src/services/alns/state.py) defines `RoutingState`, the mutable solution the
search evolves. It holds almost nothing:

```
RoutingState
  worker_routes : { worker_id → [order_id, …] }   ← the ONLY thing operators mutate
  unassigned    : [ order_id, … ]                  ← orders with no worker yet
  problem_data  : (shared, immutable)
  penalties / thresholds : resolved config for this solve
  _derived      : cached DerivedSchedule (dropped on every mutation)
```

`assign()` / `unassign()` mutate the sequences and **invalidate** the derived cache. `copy()`
deep-copies only the sequences (ProblemData stays shared).

**The derive pass — `derive_driver_routes()`** — is where the DARP magic happens. It is
deterministic and **never hard-fails**; it always assigns *some* driver and reports lateness so
the cost function can price it:

```
derive_driver_routes():

  1. WORKER TIMELINE   For each worker sequence, walk order→order from shift_start:
     _compute_visits()   arrival = clock + travel_time[hour][prev][next]
                         service_start = max(arrival, timewindow_start)   → wait
                         service_end   = service_start + duration
                         tardiness     = max(0, service_end − timewindow_end)
                         ⇒ emit a TransportEvent for each leg the worker needs moved

  2. POOL EVENTS        Group transport events that share a DESTINATION H3 zone
     _pool_events()      AND fall in the same POOL_WINDOW_MIN time bucket
                         (single hash-bucket pass; disabled ⇒ one leg per rider)

  3. SPLIT TO CAPACITY  Chunk any pool bigger than the largest vehicle's seats
     _split_to_capacity()

  4. ASSIGN DRIVERS     For each (pooled) group, _pick_driver(): the driver who can
     _pick_driver()      deliver EARLIEST — deadhead to pickup, then carry to dest —
                         whose vehicle seats the whole group and whose type they can
                         drive. Advance that driver's free-time + position.
                         No eligible driver ⇒ mark riders fully delayed (infeasible).

  ⇒ DerivedSchedule { legs, visits_by_worker, delayed_events }
```

All times are handled as **seconds-since-midnight** floats, keeping the arithmetic trivial.

### 7.5 The Cost Function

The objective in [cost.py](../src/services/alns/cost.py) is **modular**: it's a sum of
independent `CostComponent`s. Adding a constraint later means writing one subclass and appending
it to `COST_COMPONENTS` — `compute_cost` never changes.

```
objective f(s) = Σ component.evaluate(s)      (lower is better)

  TravelTimeCost          total driver shuttle time (derived legs)
  FuelCost                Σ  distance_km × fuel_average × fuel_price   (per leg's vehicle)
  TardinessCost           lateness beyond time windows      × tardiness_per_min
  OvertimeCost            work past shift_end                × overtime_per_min
  SkillViolationCost      safety net (should be ~0)          × skill_violation
  UnservedOrderCost       |unassigned|                       × unserved_order
  ExcessWaitCost          wait/pickup delay beyond threshold × excess_wait_per_min
  ShuttleInfeasibilityCost transport events no driver could deliver in time × shuttle_infeasible
```

Every weight/threshold is read from `state.penalties` — resolved from
[config.py](../src/core/config.py) defaults, optionally overridden per run. **Tuning is data,
not code.** The shuttle-derived terms (travel, fuel, wait, infeasibility) all read the cached
`derive_driver_routes()` output, so a single derive pass feeds many components.

> See [DATA_AND_CONFIG_REFERENCE.md](DATA_AND_CONFIG_REFERENCE.md) for the current penalty
> values and what each grace threshold means.

### 7.6 Destroy & Repair Operators

ALNS improves a solution by repeatedly **destroying** part of it and **repairing** it a new way.
Operators live in [operators/](../src/services/alns/operators/).

> **Contract:** the `alns` library does *not* defensively copy — it holds current = best =
> initial as the same object. So every **destroy** operator calls `state.copy()` first, then
> mutates freely. Repair operators receive that destroyed copy and mutate it in place.

**Destroy** — [destroy.py](../src/services/alns/operators/destroy.py) — removes a configurable
fraction (`destroy_pct_range`) of assigned orders back into `unassigned`:

| Operator              | Removes…                                                            |
|-----------------------|--------------------------------------------------------------------|
| `random_removal`      | N random orders — diversity anchor.                                |
| `worst_removal`       | Orders with the highest (tardiness + wait) — attacks the timeline. |
| `shuttle_cost_removal`| Orders whose shuttle leg was most delayed — DARP-specific; targets exactly what the infeasibility/wait costs flagged. |

**Repair** — [repair.py](../src/services/alns/operators/repair.py) — reinserts every unassigned
order at some `(worker, position)`, **hard-filtered by skill**. Two cost models:

| Operator                          | Scoring                                         | Speed        |
|-----------------------------------|-------------------------------------------------|--------------|
| `greedy_insertion`                | cheap **proxy**: marginal worker-timeline cost  | fast (default) |
| `regret2_insertion`               | proxy, but places high-**regret** orders (few options) first | fast |
| `shuttle_aware_greedy_insertion`  | **true objective delta** via a full derive per candidate | accurate, slower |

The proxy vs. shuttle-aware trade-off was measured (see the docstring in
[solver.py](../src/services/alns/solver.py)): shuttle-aware wins ~3.6 % on objective quality
despite ~35 % fewer iterations. Default is `proxy` for speed on large instances;
`shuttle_aware` is available for best quality on smaller ones.

### 7.7 The ALNS Loop

[solver.py](../src/services/alns/solver.py) wires everything into the `alns` library's loop:

```
solve(pd):
   initial = greedy_insertion(empty_state(pd))      ← complete starting solution
   ALNS(rng)
     + destroy operators  (the 3 above)
     + repair operators   (2, or 3 if shuttle_aware)
     select = SegmentedRouletteWheel(scores=[5,2,1,0.5], decay=0.8)   ← adaptive weights
     accept = SimulatedAnnealing(start=100 → end=1, step=0.9995)      ← escapes local minima
     stop   = MaxRuntime(max_runtime_sec)                             ← wall-clock budget

   result = alns.iterate(initial, select, accept, stop)
   return SolveResult(best, initial_obj, best_obj, improvement_pct, iterations, breakdown, raw)
```

- **Adaptive selection** (roulette wheel) rewards operators that recently produced new-best /
  better solutions, so the mix self-tunes during the run.
- **Simulated annealing** acceptance lets the search take worse moves early (high temperature)
  to escape local optima, then tightens as it cools.
- **Progress streaming:** all four outcome callbacks (`on_best`/`on_better`/`on_accept`/
  `on_reject`) feed a throttled emitter that publishes `best`/`progress` snapshots every
  N iterations — so the SSE stream shows continuous activity, not just rare new-best events.
  The emitter must never raise (it can't be allowed to break a solve).

### 7.8 Persistence & Diagnostics

[persistence.py](../src/services/alns/persistence.py) writes the winning `RoutingState` into the
four output tables and stamps the plan:

```
persist_solution(best_state):
   derive once → sched
   for each worker with visits:
      WorkerAssignment           (worker_id + worker_type)
        └ WorkerAssignmentStop   (one per served order, with est. service times)
   for each driver's legs (sorted by departure):
      DriverRoute                (+ stitched road GeoJSON if OSMnx routed it)
        ├ DriverRouteStop depot_start
        ├ DriverRouteStop dropoff … (linked back to each rider's service stop)
        └ DriverRouteStop depot_end
   stamp RoutePlan: status=ready, objective_value, totals, solver_diagnostics, optimized_at
```

The **diagnostics blob** (`build_diagnostics`) is deliberately rich — it's what the frontend's
"solver internals" view renders: the per-iteration objective trace (the cost graph), the
running best-so-far line, adaptive operator counts (new-best/better/accepted/rejected per
operator), the final cost breakdown, timing, and a best-effort reason for each unserved order
(`no_feasible_skill` vs `no_capacity_or_time_fit`).

---

## 8. End-to-End: Create a Plan → Dispatch

Putting the pieces together, here is the full lifecycle from the dispatcher's click to workers'
phones buzzing.

```
 DISPATCHER (web)                 BACKEND                              WORKER (mobile)
      │                              │                                      │
      │ POST /v1/route-plans         │                                      │
      │  {order_ids | planned_date}  │                                      │
      ├─────────────────────────────►│ _resolve_selection():               │
      │                              │   validate ownership, servability,   │
      │                              │   single service_date                │
      │                              │ create RoutePlan (status=optimizing) │
      │                              │ progress.create_channel(plan_id)     │
      │  202 {plan_id, stream_url}   │ background.add_task(run_solve)        │
      │◄─────────────────────────────┤                                      │
      │                              │                                      │
      │ GET .../{id}/stream (SSE)    │  ── run_solve in worker thread ──    │
      ├─────────────────────────────►│  loading → solving → best × N →      │
      │  event: loading              │  persisting → done                   │
      │  event: best {obj, iter}   ◄─┤  (each published to the channel)     │
      │  event: done {objective}     │                                      │
      │                              │                                      │
      │ GET .../{id}/map-data        │  read DriverRoute/WorkerAssignment/  │
      │ GET .../{id}/diagnostics   ◄─┤  geometry + diagnostics blob         │
      │                              │                                      │
      │ POST .../{id}/approve        │ status=dispatched; orders→assigned;  │
      ├─────────────────────────────►│ stops→pending; notify_workers() ─────┼──► push: "New route"
      │  {workers_notified}          │                                      │    GET /v1/mobile/my-assignments
      │◄─────────────────────────────┤                                      │◄───┤
```

### 8.1 Live Progress over SSE

Because the solve runs in a background **thread** but SSE is **async**, the two are bridged by an
in-process registry in [progress.py](../src/api/v1/progress.py):

```
 solver thread                     progress.py                    SSE endpoint (async)
      │                          ┌─────────────────┐                     │
 publish(event) ────────────────►│ per-plan        │                     │
      │                          │ thread-safe     │◄── loop.run_in_    ─┤ drains queue,
 finish(final) ─── + DONE ──────►│ Queue registry  │    executor(q.get)  │ yields SSE events
      │                          └─────────────────┘                     │ until DONE
```

Each route plan gets its own thread-safe `Queue`. The solver thread pushes events; the async SSE
handler drains them without blocking the event loop (via `run_in_executor`). A `DONE` sentinel
closes the stream. This is **single-process by design** — multi-worker deployments would need
Redis pub/sub, an explicit accepted trade-off for the demo.

### 8.2 Approval & Notifications

`POST /{plan_id}/approve` (in [route_plans.py](../src/api/v1/route_plans.py)) transitions a
`ready` plan to `dispatched`:

1. Its orders are marked `assigned`; each `WorkerAssignmentStop` is initialized to `pending`.
2. Worker domain-row IDs are resolved to `Employee` IDs.
3. `notify_workers()` pushes a job alert to each worker's active device tokens.

Notifications ([fcm.py](../src/services/notifications/fcm.py)) run in **two modes**: a **stub**
that logs the intended push (default, until Firebase creds are set) and a **real** FCM HTTP v1
sender. Either way, notification failures **never** break approval — dead tokens are pruned,
errors are logged and swallowed.

> Workers are **not** locked to a plan — a worker can hold jobs across multiple plans, each stop
> tracked by its own status.

---

## 9. The Mobile Flow

The Flutter app talks **only** to [mobile.py](../src/api/v1/mobile.py); the web dashboard sees
mobile-driven changes by reading the same DB state. A worker's day:

```
 login  ──► POST /v1/mobile/auth/login        → worker bearer token (Employee)
   │        POST /v1/mobile/auth/fcm-token     → register device for pushes
   │
 work  ──►  GET  /v1/mobile/my-assignments     → today's stops (dispatched plans only),
   │                                             with lat/lng, skills, ETAs, road polyline
   │        POST /v1/mobile/orders/{stop}/status  → en_route / arrived / in_progress
   │                                             (stamps actual_service_start)
   │        POST /v1/mobile/orders/{stop}/complete → completed + notes;
   │                                             rolls the Order up to `delivered`
   │
 track ──►  POST /v1/mobile/position           → batch GPS pings
   │           nurse/tech → WorkerPositionEvent
   │           driver     → VehiclePositionEvent (keyed on their vehicle)
   │
 avail ──►  POST /v1/mobile/availability        → mark self available/unavailable (+ reason)
```

**Ownership is enforced on every stop mutation:** `_load_owned_stop` resolves the caller's
worker row and rejects (`NotAssignedToYou`) any stop that isn't theirs — a worker can only touch
their own jobs.

---

## 10. Live Tracking

[tracking.py](../src/api/v1/tracking.py) powers the web dashboard's real-time map. It's
**polling-based** today (SSE is a noted future upgrade).

```
GET /v1/tracking/live
   for each company worker (nurse/tech):  latest WorkerPositionEvent
   for each company vehicle:              latest VehiclePositionEvent (+ driver contact)
   annotate each with recency:
       age > TRACKING_DROP_AFTER_MIN   → omitted entirely
       age > TRACKING_STALE_AFTER_SEC  → is_stale = true (map greys it out)
```

Naive client timestamps are treated as UTC, and a client clock slightly ahead of the server is
clamped so "seconds ago" never goes negative — small robustness touches for real-device data.

There's also a **roster** endpoint returning who's available/unavailable, why, and their contact
details — the dispatcher's view of the availability that workers set from the app in §9.

---

## 11. Cross-Cutting Concerns

- **Configuration** — everything tunable lives in [config.py](../src/core/config.py) as a
  Pydantic `Settings` loaded from `.env`: DB/Redis URLs, fuel prices, ALNS penalties/thresholds,
  pooling, tracking staleness, and the ALNS loop defaults. Any solver value can be overridden
  per-plan through `RoutePlan.optimization_params`.
- **Error handling** — typed domain exceptions in [exceptions/](../src/exceptions/) (grouped by
  area) give endpoints precise, self-documenting failures (`OrdersNotOwned`, `PlanNotReady`,
  `NotAssignedToYou`, …) instead of bare HTTP errors.
- **Schemas** — [schemas/](../src/schemas/) holds the Pydantic request/response contracts, kept
  separate from ORM models so the API surface and the database can evolve independently.
- **Migrations** — Alembic manages schema changes; `init_db()` (create-all) exists only for
  dev/testing convenience.
- **Seeding & scripts** — [utils/scripts/](../src/utils/scripts/) contains demo seeders
  (auth, dataset, zones, synthetic instances) and DB/zone visualizers.

---

## 12. Known Design Limits

These are conscious trade-offs for the demo, called out here so they aren't mistaken for bugs.
The full list lives in the future-improvements doc; the architecturally significant ones:

- **Single-process SSE** — the progress registry is in-memory; horizontal scaling needs Redis
  pub/sub.
- **No token expiry / no server-side revocation** — logout is client-side only.
- **No formal RBAC** — `SysUsers.role` is a free-text string; there's no permission model yet.
- **Auth is per-endpoint, not middleware** — each handler declares an auth dependency; a single
  middleware choke-point is planned.
- **Some services bypass repositories** with raw queries — a consistency cleanup.
- **Single-depot assumption** in the solver — every worker starts/ends at one depot; per-worker
  home starts / multi-depot (MDVRP) is future work.
- **Vehicles are transport-only** — no equipment capacity modeling yet.

---

*This document describes the backend under [src/](../src/) as of the current demo build. Pair it
with [DATA_AND_CONFIG_REFERENCE.md](DATA_AND_CONFIG_REFERENCE.md) for the schema/config detail and
[FUTURE_IMPROVEMENTS_AND_CONCERNS.md](FUTURE_IMPROVEMENTS_AND_CONCERNS.md) for the roadmap.*
