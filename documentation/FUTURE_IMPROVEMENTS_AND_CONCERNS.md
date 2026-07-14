# Nightingale — Future Improvements & Current Concerns

> A living record of known limitations, open design debates, and planned work across
> the entire Nightingale system: the **Backend API**, the **Frontend admin console**,
> the **Mobile app**, and the **ALNS routing algorithm**.
>
> Items here are *not* bugs in shipped features — they are conscious trade-offs made to
> reach a working demo, decisions still under debate, and features we know we want next.
> Each entry explains *what* the concern is and *why* it matters, so anyone technical can
> pick it up without needing the original context.

---

## Table of Contents

1. [Backend](#1-backend)
   - 1.1 [Database Models & Schema](#11-database-models--schema)
   - 1.2 [Data Access & Query Patterns](#12-data-access--query-patterns)
   - 1.3 [Auth, Access Control & Onboarding](#13-auth-access-control--onboarding)
   - 1.4 [Background Processing & Infrastructure](#14-background-processing--infrastructure)
   - 1.5 [Scheduling & Domain Logic](#15-scheduling--domain-logic)
   - 1.6 [Worker Lifecycle & Ratings](#16-worker-lifecycle--ratings)
   - 1.7 [Geocoding & Location Input](#17-geocoding--location-input)
   - 1.8 [Live Tracking Transport](#18-live-tracking-transport)
   - 1.9 [API Surface & Performance Concerns](#19-api-surface--performance-concerns)
   - 1.10 [Migrations](#110-migrations)
2. [Frontend](#2-frontend)
3. [Mobile App](#3-mobile-app)
4. [ALNS Routing Algorithm](#4-alns-routing-algorithm)
   - 4.1 [Scope Simplifications (Accepted for Now)](#41-scope-simplifications-accepted-for-now)
   - 4.2 [Modeling Gaps](#42-modeling-gaps)
   - 4.3 [Algorithmic Depth](#43-algorithmic-depth)
5. [Priority Snapshot](#5-priority-snapshot)

---

## 1. Backend

Backend source lives under [src/](../src/). Database models are in
[src/db/models/](../src/db/models/), data-access repositories in
[src/db/repositories/](../src/db/repositories/), business logic in
[src/services/](../src/services/), and the HTTP layer in [src/api/](../src/api/).

### 1.1 Database Models & Schema

- **Audit the `nullable=True` defaults.**
  Many columns across [src/db/models/](../src/db/models/) are currently nullable simply
  because it was the path of least resistance during rapid iteration. We need a pass to
  decide which fields should actually be `NOT NULL`. Over-permissive nullability lets
  bad/half-formed rows into the database and pushes validation burden onto every reader.

- **Foreign-key constraints on audit columns.**
  Audit columns (e.g. `created_by` / `updated_by`) reference users but aren't yet backed
  by real FK constraints. Without them the database can't guarantee referential integrity,
  so an audit column can point at a user that no longer exists.

- **UUID vs. integer primary keys — open debate.**
  We haven't committed to a single primary-key strategy. Integers are compact, fast to
  index, and human-readable; UUIDs avoid ID collisions across services/environments and
  don't leak row counts or ordering. This needs a decision *before* the schema hardens,
  because migrating key types later is expensive and touches every FK.

- **Improve the `__repr__` methods.**
  Model classes in [src/db/models/](../src/db/models/) have weak/auto `__repr__`
  implementations. Better reprs (showing the primary key plus a couple of identifying
  fields) make logs, debugger sessions, and test failures far easier to read.

### 1.2 Data Access & Query Patterns

- **Move to a repository-style data layer everywhere.**
  We already have repositories under [src/db/repositories/](../src/db/repositories/), but
  several services and helpers still issue raw/ad-hoc queries directly. Routing all
  database access through repositories centralizes query logic, makes it testable/mockable,
  and prevents the same query being reinvented (slightly differently) in five places.

### 1.3 Auth, Access Control & Onboarding

- **Dedicated auth middleware.**
  Authentication checks should live in a single middleware layer rather than being
  repeated per-endpoint. One choke point is easier to reason about, harder to accidentally
  bypass, and simpler to extend (e.g. token refresh, rate limiting).

- **RBAC — roles & permissions.**
  There is no real role/permission model yet. We need Role-Based Access Control so that,
  for example, a dispatcher, a company admin, and a super-admin see and do different
  things. This underpins almost every future multi-tenant feature.

- **New-user / onboarding flow.**
  There's currently no guided path for creating and setting up a brand-new user or company
  (invite → verify → configure). Needed before the system can be handed to real customers
  rather than seeded demo accounts.

### 1.4 Background Processing & Infrastructure

- **Introduce Celery for background tasks.**
  Long-running work — most importantly map/matrix computation and caching — should run
  asynchronously off the request path via a task queue (Celery). Today anything heavy risks
  blocking or timing out a request. Related caching artifacts already exist under
  [cache/](../cache/) and [map_cache/](../map_cache/).

- **Self-hosted map server (under consideration).**
  We currently depend on external routing/map services (see [src/services/maps.py](../src/services/maps.py)
  and [src/services/matrix.py](../src/services/matrix.py)). Running our own map/routing
  server would cut per-request cost, remove rate limits, and improve latency and privacy —
  but it's a real operational commitment. Flagged as a *maybe*, pending cost/benefit.

### 1.5 Scheduling & Domain Logic

- **Handle multi-date orders instead of rejecting them.**
  Right now, if an order spans multiple dates when selected for scheduling, we reject it.
  We should instead split or span it across the relevant planning days so these orders can
  actually be scheduled rather than bounced back to the user.

- **Make penalties and weights configurable via API/frontend.**
  The ALNS cost function relies on tunable penalties/weights (see
  [src/services/alns/cost.py](../src/services/alns/cost.py) and the cost-profile model
  [src/db/models/cost_profile.py](../src/db/models/cost_profile.py)). These are effectively
  hard-coded/seeded today. Exposing them through the API and UI lets operators tune
  behavior (e.g. "prioritize punctuality over vehicle count") without a code change.

- **Well-named route plans.**
  Route plans need human-friendly, meaningful names rather than opaque IDs/timestamps, so
  operators can find and refer to them. (Also raised in the Frontend section.)

### 1.6 Worker Lifecycle & Ratings

- **Separate "unavailable" from "suspended" — open debate.**
  The `suspended` status was intended for workers the company has deemed unfit. But workers
  who simply mark *themselves* unavailable currently risk landing in that same bucket, which
  wrongly conflates "I'm off today" with "the company benched you." We should either add a
  new `unavailable` enum value or repurpose `suspended` → `unavailable`. Needs a decision on
  semantics before we build UI/reporting on top of it.

- **Unavailability: DB seed vs. live app state — possible clash.**
  There's a concern that a worker seeded as unavailable in the database could conflict with
  the app already treating them as unavailable, producing a double/contradictory state. Worth
  confirming whether this is a real bug or a non-issue.

- **Worker ratings algorithm & computation.**
  We need a defined algorithm for how a worker's rating is computed (punctuality, completion
  rate, customer feedback, etc.) and where/when it's recalculated.

- **Plan ratings with reasoning — two-sided.**
  For each generated plan we want two kinds of feedback:
  1. **From the user** — why a plan was good or bad (structured feedback we can learn from).
  2. **From the system** — an explanation of *why the algorithm made the choices it did*
     (transparency / explainability), so a rejected plan isn't a black box.

### 1.7 Geocoding & Location Input

- **Use Photon for nearby-location lookup.**
  Integrate [Photon](https://photon.komoot.io/) (or similar) to resolve and suggest nearby
  places, so users search for locations by name/address.

- **Stop asking for raw lat/lng on the orders page.**
  Requiring users to type raw coordinates when creating orders is error-prone and unfriendly.
  Coordinates should come from a geocoded address / map pick instead. (Pairs with the Photon
  item above.)

### 1.8 Live Tracking Transport

- **Polling vs. SSE for live tracking — decision needed.**
  Live position updates (see position-event models
  [src/db/models/vehicle_position_event.py](../src/db/models/vehicle_position_event.py) and
  [src/db/models/worker_position_event.py](../src/db/models/worker_position_event.py)) can be
  delivered by client polling or by Server-Sent Events. Polling is simple but chatty; SSE is
  more efficient and near-real-time but adds connection-management complexity. We should pick
  one deliberately rather than defaulting.

### 1.9 API Surface & Performance Concerns

- **Investigate excessive `GET` calls on the route-plans API.**
  The route-plans endpoints appear to be called far more than expected. We need to find the
  source (over-eager refetching on the frontend? missing caching? a render loop?) and fix it,
  as it likely wastes server work and bandwidth.

- **Complete CRUD APIs for core entities.**
  We still need full create/read/update/delete coverage for **companies, workers, fleet,
  drivers, and depots**. Some of these only have partial endpoints today, which blocks admin
  workflows and the onboarding flow above.

- **Search mechanism.**
  There's no general search across entities (orders, workers, plans, etc.). Needed for the
  console to remain usable as data volume grows.

### 1.10 Migrations

- **Resolve isolated / multiple Alembic heads.**
  The Alembic migration history has branched into isolated heads. Multiple heads mean
  `upgrade` becomes ambiguous and environments can drift. We need to merge the heads back
  into a single linear (or cleanly merged) history and keep it that way.

---

## 2. Frontend

Frontend source lives under [frontend/src/](../frontend/src/), with route pages under
[frontend/src/pages/](../frontend/src/pages/).

- **Settings page.**
  A dedicated settings area is missing — needed for user/company preferences and (eventually)
  for exposing the configurable ALNS penalties/weights described in section 1.5.

- **Logos & branding.**
  Add proper Nightingale logos and brand assets throughout the app.

- **Improved, line-art-styled UI.**
  Move the visual design toward the cleaner, line-art aesthetic shown in the reference
  images, rather than the current placeholder styling.

- **Worker profile pictures & illustrations.**
  Support worker profile photos and use vector "people" illustrations as tasteful
  placeholders where a photo is absent.

- **Route-plan naming in the UI.**
  Surface the human-friendly plan names (see section 1.5) so users can browse and pick plans
  by name, not by ID.

- **Responsive sizing.**
  Fix layout/sizing issues that appear across different screen sizes and resolutions — some
  views don't scale cleanly yet.

---

## 3. Mobile App

The mobile app is the field-facing companion for drivers/workers.

- **Attendance feature.**
  Let workers clock in/out or mark presence from the app — feeds into scheduling and
  availability.

- **Past order history.**
  Give workers a view of the jobs/orders they've previously completed.

- **Ratings & profile page.**
  A profile screen showing the worker's own rating (see the ratings algorithm in section 1.6)
  and editable profile details.

- **Stats & dashboard.**
  A personal dashboard with the worker's key stats (jobs done, distance, punctuality, etc.).

- **App logos & icons.**
  Proper app icon and in-app branding assets.

- **Explicit on-screen errors — technical *and* non-technical.**
  When something fails, the app should show a clear, human-readable message (for the worker)
  while still capturing the technical detail (for support/debugging). Silent failures or raw
  stack traces are both unacceptable in the field.

---

## 4. ALNS Routing Algorithm

The routing engine is an Adaptive Large Neighborhood Search solver living under
[src/services/alns/](../src/services/alns/) — key pieces include
[solver.py](../src/services/alns/solver.py), [state.py](../src/services/alns/state.py),
[cost.py](../src/services/alns/cost.py), [problem_data.py](../src/services/alns/problem_data.py),
and the [operators/](../src/services/alns/operators/) directory.

### 4.1 Scope Simplifications (Accepted for Now)

These are deliberate simplifications for the demo — documented so they aren't mistaken for
oversights.

- **Idle workers carry no cost.**
  Leaving a worker unassigned currently incurs *no* penalty to the company, so the solver is
  free to not use a worker. This is considered fine for now; a future cost model might treat
  idle-but-paid workers as a real cost to minimize.

- **Vehicles are transport-only.**
  Vehicles are modeled purely as a way to move workers around — they don't yet carry
  tools/equipment with capacity constraints. Equipment-carrying (and the capacity math that
  comes with it) is a later addition.

### 4.2 Modeling Gaps

- **Lunch breaks / mandatory rest.**
  The schedule doesn't yet reserve time for lunch or required breaks. Real shifts need them,
  and they affect feasible time windows.

- **Road restrictions are ignored.**
  The router does not account for one-way/two-way streets, max height/width limits, broken or
  closed roads, or truck-friendly routing. Today it assumes an idealized network. Real-world
  restriction data is a future integration.

- **Single shared depot assumption.**
  Every worker is currently assumed to start (and end) at one central depot. In reality
  workers may start from their **home**, a **different depot** (a Multi-Depot VRP / MDVRP
  scenario), or other spots. Supporting per-worker start locations is a significant but
  important generalization.

### 4.3 Algorithmic Depth

- **Proper DARP math & implementation.**
  The current design is DARP-inspired (Dial-A-Ride Problem) but not a full, rigorous DARP
  formulation. A future pass should tighten the mathematical model and its implementation to
  match true DARP semantics (pickup/dropoff pairing, ride-time constraints, etc.).

- **ML-based clustering of job/order nodes.**
  Introduce machine-learning clustering to group nearby service nodes (where workers must
  travel to perform a job). Good clusters shrink the search space and tend to produce better,
  more geographically coherent routes for the ALNS solver to refine.

---

## 5. Priority Snapshot

A rough, non-binding view of what's most load-bearing for moving past the demo. Reorder as
priorities shift.

| Area      | High-impact / near-term                                              | Needs a decision first                          |
|-----------|---------------------------------------------------------------------|-------------------------------------------------|
| Backend   | Auth middleware, RBAC, repository-style data access, Alembic heads  | UUID vs. int PKs; `unavailable` vs. `suspended` |
| Backend   | Full CRUD for companies/workers/fleet/drivers/depots; onboarding    | Polling vs. SSE for live tracking               |
| Frontend  | Settings page, responsive sizing, route-plan naming                 | Line-art design direction                       |
| Mobile    | Explicit on-screen errors, attendance, order history                | —                                               |
| ALNS      | Per-worker start locations (MDVRP), road restrictions               | Full DARP formulation; ML clustering scope      |

---

*This document is intended to be updated as items are resolved or reprioritized. When an item
ships, move it out of here and into the changelog / relevant build docs rather than deleting the
context silently.*
