# Nightingale — Frontend Brief for Claude Design

**What you are building:** the **web admin/dispatcher console** for Nightingale, a field-service routing platform. It's a React web app that a company's operators use to manage their orders, customers, fleet, and field workers; create optimized route plans via an AI solver; watch the solver work in real time; approve plans; and monitor live operations.

**What you are NOT building:** the mobile field-ops app. That's a separate Flutter app for the nurses/technicians/drivers in the field — it is not in this codebase and shares no code with your frontend. It is mentioned in this doc only so you understand *why* some data changes on its own (a nurse marks a job done in the field → an order flips to `delivered` → your dashboard reflects it on next poll). You never call the mobile endpoints.

**Who reads this doc:** you (Claude Design). Read it top-to-bottom. It gives you the backend contract (auth, endpoints, data shapes, enums, errors), the intended UX per area, and a suggested screen map. The live, machine-readable API schema is at **`/docs`** (Swagger/OpenAPI) and **`/openapi.json`** on the running backend — use it as the exact source of truth for request/response fields; this doc gives you the *meaning and intent* behind them.

---

## 0. Non-negotiables (read first)

The product owner is **not a frontend developer** and will only evaluate look-and-feel / UX. **You own code quality and correctness.** Therefore:

- **Build it like a senior frontend team would ship it.** Modular, industry-standard, maintainable by future devs.
- **A single typed API client layer.** All backend calls go through one place (e.g. `src/api/`), with typed request/response models generated from or mirroring the OpenAPI schema. UI components never call `fetch` directly.
- **Real state management** (React Query / TanStack Query is ideal here — the app is read-heavy with polling and background mutations). Server state cached and invalidated properly; don't hand-roll loading flags everywhere.
- **Every data view handles all states:** loading, empty, error, and success. Never a blank screen on error — show the backend's error message (see §7).
- **Auth is global and enforced.** An unauthenticated user is redirected to login; the token is attached to every request; a 401 sends them back to login.
- **Environment-config the API base URL** (don't hardcode `localhost`).
- **Accessibility + responsive**: it's a desktop-first console but must not break on smaller windows.
- **Componentize aggressively**: tables, forms, cards, the map, the live-metrics panel — all reusable.

You have visual reference images (provided separately) — follow their look/feel. This doc does **not** prescribe visuals; it prescribes structure, data, and flows.

---

## 1. The domain in one screen

Nightingale optimizes **field-service routing** for a company that sends either **nurses** or **technicians** (never both — a company is one `service_type`) to perform **orders** (jobs) at customer locations. Workers don't drive themselves — **drivers** shuttle them between jobs in **vehicles** (this is a dial-a-ride problem). An **AI solver (ALNS)** computes who serves which order, in what sequence, and how drivers shuttle them — optimizing travel time, fuel, punctuality, and driver ride-sharing.

The operator's job (your app): keep the data current, trigger a solve for a chosen day's orders, watch it optimize live, approve the result (which dispatches it to the field workers' phones), and monitor the day's operations.

**Key entities:**
- **Company** — the tenant. Has a `service_type` (`nurse` or `technician`). The logged-in operator belongs to one company; everything is scoped to it automatically.
- **Customer** — who orders are for. Has a location.
- **Order** — one job at a location on a `service_date`, needing certain skills, with an optional time window. This is the unit of work.
- **Employee** — a field worker's identity (name, contact, shift, availability). Backs a nurse/technician/driver.
- **Nurse / Technician** (a "worker") — performs orders; has skills. Which one exists depends on company `service_type`.
- **Driver** — shuttles workers; drives a vehicle.
- **Vehicle** — transport; has a seating capacity (enables ride-sharing).
- **Depot** — where drivers/workers start the day.
- **Route Plan** — one solve for one day's selected orders. Goes `draft → optimizing → ready → dispatched`. Holds the solver result + rich diagnostics.

---

## 2. Auth & session

**Login:** `POST /v1/auth/login` with `{username, password}` → `{token, user}`. The `user` has `{id, username, role, company_id, ...}`.

- Store the token; attach it as `Authorization: Bearer <token>` on **every** subsequent request.
- **`company_id` is never sent by the frontend** — the backend derives it from the token. All list/detail endpoints are automatically scoped to the operator's company. (This is why no endpoint takes a `company_id` param.)
- `GET /v1/auth/me` → re-fetch the current user (use to restore session on reload).
- `POST /v1/auth/logout` → tells the backend; then drop the token client-side and go to login.
- **On any 401** (`error_code: invalid_token` / `not_authenticated`): clear session, redirect to login.

**Demo credentials** (seeded): `admin1` / `password` (a nurse company), `admin2` / `password` (a technician company). Use `admin1` for most development.

---

## 3. The core flow (the heart of the app)

This is the primary user journey — design it to feel great:

```
1. Operator logs in → lands on Dashboard (today's ops at a glance)
2. Goes to Orders → sees today's & upcoming servable orders
3. Creates a Route Plan → selects a set of orders (all same date) → clicks "Optimize"
4. → Plan Detail opens in "optimizing" state
   → a LIVE panel/sidebar streams the solver working: objective dropping in
     real time, operator weights, cost breakdown, iteration count
   → when done, the optimized routes + map + unserved list appear
5. Operator reviews, then clicks "Approve" → plan is dispatched to field workers
6. Operator monitors: live worker/vehicle positions on a map, order statuses
   updating as field workers complete jobs, the availability roster
```

The **live solver panel** (step 4) is the one "technical" flourish the product owner wants — see §5.

---

## 4. Endpoint reference (web console)

All under `/v1`. Auth required (Bearer token) unless noted. Full field-level schemas: **`/openapi.json`**. Below is purpose + UX intent + the shape that matters.

### 4.1 Meta / reference

- **`GET /v1/meta/enums`** — all enum values + the company's applicable skills. **Call once on app load**, cache it, and use it to populate every dropdown / status filter / label. Never hardcode enum values in the frontend — read them from here. Returns e.g. `order_status`, `order_priority`, `vehicle_type`, `fuel_type`, `nurse_skills`, `technician_skills`, `applicable_skills` (the ones this company uses), etc. (Canonical values also listed in §6.)

### 4.2 Dashboard

- **`GET /v1/dashboard/today?date=YYYY-MM-DD`** (date optional, defaults today) — the landing summary. Returns: `orders_today`, `order_status_counts` (pending/assigned/in_transit/delivered/failed), `completion_pct`, `plans_today`, `plan_status_counts`, `workers_total/available/unavailable`, `drivers_total`, `vehicles_total`.
  - **UX:** hero of the Dashboard screen — stat cards, a completion ring/progress, status breakdowns. Poll every ~10s so it stays live as field workers complete jobs.

### 4.3 Orders (full CRUD + the picker)

- **`GET /v1/orders`** — all orders (management/history view). Rich: each includes `customer_name`, `customer_phone`, `lat/lng`, `address_text`, `status`, `priority`, `service_date`, skills, time window, etc.
- **`GET /v1/orders/servable?from_date=&to_date=`** — **the order picker** for creating a plan: pending/assigned orders, today-onward. This is what you show when the operator is choosing orders to optimize. Group by `service_date` (the operator picks orders from ONE date per plan).
- **`GET /v1/orders/{id}`**, **`POST /v1/orders`**, **`PUT /v1/orders/{id}`**, **`DELETE /v1/orders/{id}`** — standard CRUD.
  - Create needs `customer_id`, `service_date`, a location (`location_id` OR `lat`+`lng`), `required_skills` (must be valid for the company's service_type — get them from `/meta/enums.applicable_skills`), optional `priority`, time window, `service_duration_min`.
  - **UX:** an Orders table (sortable/filterable by status, date, priority), a create/edit form, a detail view. Status is color-coded (see §6). Location can be picked on a small map or entered as lat/lng.

### 4.4 Route Plans (the solver)

- **`POST /v1/route-plans`** — **create + trigger a solve.** Body: `order_ids: [int]` (the operator's selection — all must share one `service_date`, which becomes the plan date) OR `planned_date` (solve all servable orders that day). Optional `repair_mode` (`"proxy"` fast | `"shuttle_aware"` higher quality), `config_overrides` (solver tuning, e.g. `{"max_runtime_sec": 30}`), `name`. Returns `{route_plan_id, status: "optimizing", planned_date, order_count, stream_url}`.
  - **Right after this, open the SSE stream (§5) to show live progress.**
  - Rejects (400) with clear `error_code` if the selection is bad (see §7): mixed dates, orders not owned, non-servable, etc.
- **`GET /v1/route-plans`** — plan history (newest first). List view with status, date, objective, order/route/unserved counts.
- **`GET /v1/route-plans/{id}`** — plan summary: status, `objective_value`, `total_orders`, `total_routes`, `total_unserved`, `optimized_at`.
- **`GET /v1/route-plans/{id}/stream`** — **SSE live progress** (see §5).
- **`GET /v1/route-plans/{id}/diagnostics`** — the full solver telemetry for the live/results panel (see §5). 409 if not solved yet.
- **`GET /v1/route-plans/{id}/driver-routes`** — one row per driver's day: `driver_id`, `vehicle_id`, `total_distance_m/time_sec`, and ordered `stops` (each with `stop_type`, `lat/lng`, `eta/etd`, distances).
- **`GET /v1/route-plans/{id}/worker-assignments`** — one row per worker's day: `worker_id`, `worker_type`, and ordered `stops` (each an order with `lat/lng`, estimated service times).
- **`GET /v1/route-plans/{id}/unserved`** — orders the solver couldn't place: `[{order_id, reason}]` (reasons like `no_feasible_skill`). **Show this prominently** — unserved orders are a real operational failure the operator must see and act on.
- **`GET /v1/route-plans/{id}/map-data`** — everything for the **solver route map** (a must-have screen, §8b) in one call:
  - `depot: {lat, lng, location_id}`
  - `driver_routes: [{driver_route_id, driver_id, driver_name, vehicle_id, vehicle_plate, total_distance_m, total_time_sec, points: [{seq, stop_type, lat, lng}], geometry}]` — `geometry` is the **real road-following polyline** (GeoJSON `LineString`/`MultiLineString`, `[lng, lat]`) to draw for each driver; `driver_name` + `vehicle_plate` are for the **legend**. If a solve fell back to straight-line mode, `geometry` is `null` — draw straight lines between `points` instead.
  - `order_markers: [{order_id, lat, lng, served (bool), worker_id}]` — served vs. unserved markers.
- **`POST /v1/route-plans/{id}/approve`** — **approve a `ready` plan.** Flips it to `dispatched`, marks its orders `assigned`, and pushes the assignments to the field workers' phones (via the mobile app / push). Returns `{status, orders_marked_assigned, workers_notified, notify_mode}`. 409 if already dispatched or not `ready`.
  - **UX:** a prominent "Approve & Dispatch" button on a `ready` plan, with a confirmation. After approval the plan is read-only and monitoring begins.
- **`DELETE /v1/route-plans/{id}`** — delete a draft/ready/failed plan (409 for dispatched/completed).

### 4.5 Map geometry note

`map-data` and `driver-routes` geometry is **GeoJSON** with coordinates in **`[longitude, latitude]`** order (GeoJSON standard) — mind the order when feeding a map library (most expect `[lat, lng]` or have a GeoJSON mode). Geometry may be a `LineString` or `MultiLineString`. If a solve fell back to straight-line mode, geometry may be absent — draw straight lines between stop points as a fallback.

### 4.6 Fleet & workforce (full CRUD)

All company-scoped, all with list/detail/create/update/delete, all with **rich joined reads** (you won't need N+1 calls):

- **`GET /v1/customers`** (+ CRUD) — includes location + `order_count`.
- **`GET /v1/vehicles`** (+ CRUD) — includes `depot_name`, `assigned_driver_id`, capacity, fuel, etc.
- **`GET /v1/drivers`** (+ CRUD) — includes the driver's `name`/contact (from their Employee), `vehicle_plate`, `skills` (vehicle types they can drive), availability.
- **`GET /v1/workers`** (+ CRUD) — the nurses OR technicians (backend picks by company type). Includes `name`/contact, `skills`, `operational_status`, `unavailable_reason`, shift. `worker_type` tells you which.
- **`GET /v1/employees`** (+ CRUD) — the underlying identity records; includes derived `role` (nurse/technician/driver) and `has_login`. Most consoles surface workers/drivers directly rather than raw employees, but the CRUD is here if you want an "all staff" view.
- **`GET /v1/depots`** (+ CRUD) — includes location.
- **`GET /v1/company` / `PUT /v1/company`** — view/edit the operator's own company (name, contact, timezone). No create/delete.

### 4.7 Live operations (monitoring — poll these)

- **`GET /v1/tracking/live`** — latest known GPS position of each active worker and vehicle, enriched for map popups + recency. Returns `{positions: [...], as_of, stale_after_sec}` where each position is `{subject_type (nurse|technician|driver|vehicle), subject_id, name, lat, lng, recorded_at, employee_id, employee_code (e.g. "EMP-42"), contact_number, seconds_ago, is_stale}`. See **§8a — the Live Tracking map** (a must-have screen). Positions come from the field workers' mobile app; there may be none until workers are on-shift. Positions older than 24h are omitted; positions older than `stale_after_sec` come back with `is_stale: true`.
- **`GET /v1/tracking/availability`** — the **availability roster**: every worker with `name`, `role`, `contact_number/email`, `operational_status`, `available` (bool), `unavailable_reason`, `since`. **UX:** a roster panel showing who's available vs. out (and why + how to reach them). Workers mark themselves unavailable from the field app; this is how the operator sees it.

---

## 5. The live solver panel (the one "technical" view)

The product owner wants technical viewers to **watch the AI solver work in real time** — rendered as a **card / right-side sidebar** on the Route Plan Detail screen while a solve runs (and viewable afterward from stored diagnostics). This is a signature feature — make it feel alive.

**Two data sources:**

**(a) Live stream — `GET /v1/route-plans/{id}/stream` (SSE / EventSource).** After creating a plan, open this. It emits JSON events (`data:` lines). Event `type`s:
- `loading` — `{message}` — loading road network + data.
- `solving` — `{message, orders, workers, drivers, vehicles}` — solve started.
- `best` — `{iteration, current_objective, best_objective, elapsed_sec}` — a new best solution found. **Plot these** — this is the objective dropping over time (the money graph).
- `progress` — same shape, emitted periodically even without improvement, so the graph keeps moving.
- `persisting` — `{message}` — writing results.
- `done` — `{status, best_objective, initial_objective, improvement_pct, iterations, total_unserved}` — finished; now fetch the full result + diagnostics.
- `error` — `{error_code, message}` — solve failed (e.g. `location_unroutable`). Show the message.
- `warning` — `{message}` — non-fatal (e.g. road network unavailable, using estimates).
- `close` — stream is ending; close the EventSource.

**UX for the live panel:**
- A **real-time line chart** of `best_objective` (and/or `current_objective`) vs. iteration/time — the audience watches the cost fall. This is the hero.
- A live readout: current iteration, elapsed, current best objective, % improvement so far.
- Status ticker: loading → solving → persisting → done.

**(b) Final diagnostics — `GET /v1/route-plans/{id}/diagnostics`** (after `done`, and for any past solved plan). A rich JSON blob:
- `summary` — `initial_objective`, `best_objective`, `improvement_pct`, `iterations`, `runtime_sec`, `iters_per_sec`, `total_orders/assigned/unserved`, `workers_used/idle`.
- `cost_breakdown` — the objective split by component: `travel_time`, `fuel`, `tardiness`, `overtime`, `skill_violation`, `unserved`, `excess_wait`, `shuttle_infeasible`. **UX:** a bar/donut showing what's driving the cost.
- `penalties_used` — the penalty weights this solve used.
- `iteration_trace` — `{objectives: [...per iteration], best_so_far: [...], runtimes: [...], num_iterations}`. **UX:** the full objective curve (redraw the live chart from this when viewing a finished plan).
- `operator_stats` — `{destroy: {op_name: {counts, new_best, better, accepted, rejected, total_used}}, repair: {...}}`. **UX:** show which solver operators (destroy/repair heuristics) were used and how effective each was — a small table or bar chart per operator. This is the "operator weights/values" the owner mentioned.
- `unserved` — `[{order_id, reason}]`.

**Design intent:** a technical person glancing at the sidebar should immediately grasp "the solver is trying thousands of options, the cost is dropping, here's what it's optimizing and which strategies are working." Keep it legible, not overwhelming — it's a confidence-builder, not a control panel.

---

## 6. Enums (with meaning) — for labels, colors, filters

Fetch canonical values live from `GET /v1/meta/enums`. Meanings for UI:

**OrderStatus** `pending → assigned → in_transit → delivered` (or `failed`). `pending` = not yet in a plan; `assigned` = in an approved plan; `in_transit`/`delivered` = field worker updates; `failed` = couldn't complete. Color-code (e.g. grey→blue→amber→green, red for failed).

**OrderPriority** `low | normal | high | urgent`. Show as a badge; urgent stands out.

**PlanStatus** `draft | optimizing | ready | dispatched | completed | failed`. `optimizing` = solve running (show the live panel + spinner); `ready` = solved, awaiting approval (show Approve button); `dispatched` = approved & sent to field (read-only, monitor); `failed` = solve errored (show why).

**WorkerStopStatus** (a field worker's per-job state, seen in monitoring) `pending | en_route | arrived | in_progress | completed | failed`.

**OperationalStatus** `active | suspended | inactive`. `active` = available; `suspended` = worker marked themselves unavailable (has a reason); `inactive` = not in service.

**ServiceType** `nurse | technician` — the company's mode. Determines which skill set applies and whether you show "Nurses" or "Technicians" in the UI.

**VehicleType** `bike | car | van | truck`. **FuelType** `petrol | diesel | electric | cng`.

**NurseClinicalSkill** `iv_administration | phlebotomy | wound_care | triage | ventilator_management | dialysis`.
**TechnicianSkills** `network_setup | hardware_installation | cable_management | system_configuration`.
(Show only the set matching the company's `service_type` — use `applicable_skills` from `/meta/enums`. Render as chips.)

---

## 7. Error handling (contract)

Every error response has a consistent shape in `detail`:

```json
{ "detail": { "error_code": "stable_snake_case_code", "message": "Human-readable message." } }
```

**Always surface `message` to the user**; branch on `error_code` when you want special handling. Key codes:

- `invalid_credentials` (401) — bad login.
- `invalid_token` / `not_authenticated` (401) — **clear session, go to login.**
- `cross_company_access` (403) — tried to access another tenant's resource (shouldn't happen in normal UI).
- `<entity>_not_found` (404) — e.g. `customer_not_found`, `order_not_found`, `route_plan_not_found`.
- `validation_failed` (400) — bad input (message explains).
- Order-selection (on plan create): `orders_not_found`, `orders_not_owned`, `orders_not_servable`, `orders_missing_service_date`, `orders_span_multiple_dates` (they picked orders across dates — tell them one plan = one day), `planned_date_mismatch`, `selection_missing`, `no_servable_orders`.
- Plan lifecycle: `plan_not_ready`, `plan_already_dispatched`, `plan_not_deletable`, `no_diagnostics`.
- Solve failure (via SSE `error` event): `location_unroutable` (an order's location is off the serviceable map — the operator must fix the address), `solve_failed`.

Standard FastAPI validation errors (422) come as `detail: [{loc, msg, ...}]` — handle that shape too (show a generic "please check your input").

---

## 8. Suggested screen map (structure, not visuals)

Design the IA/layout as you see fit with the reference images. A sensible set:

- **Login** — outside the app shell.
- **App shell** — persistent nav (Dashboard, Orders, Route Plans, Fleet, Workers, Tracking) + top bar (company name, current user, logout). Everything below lives inside it.
- **Dashboard** — today's stat cards, completion ring, status breakdowns, quick links (create plan, view unserved). Polls `/dashboard/today`.
- **Orders** — table (filter by status/date/priority), create/edit form, detail. Uses `/orders` CRUD.
- **Route Plans** — list/history (`/route-plans`) + a **"New Plan"** flow: order picker (`/orders/servable`, group by date) → choose orders → optimize → **Plan Detail**.
- **Plan Detail** — the richest screen:
  - While `optimizing`: the **live solver sidebar/card** (§5) with the real-time objective chart + metrics; main area shows a "solving…" state.
  - When `ready`/`dispatched`: **map** (routes as polylines from `map-data`, order markers, depot), **driver-routes** table, **worker-assignments** table, **unserved** list, and the **diagnostics** panel (cost breakdown, operator stats, final objective curve). **Approve** button when `ready`.
- **Fleet** — Vehicles + Drivers + Depots (tabs or sections), each CRUD.
- **Workers** — the nurses/technicians roster + CRUD; surfaces skills, shift, availability.
- **Tracking / Live Ops** — see §8a below + the **availability roster** (`/tracking/availability`) + today's order-status board. Polls.

### 8a. Live Tracking map (MUST-HAVE, its own tab)

A dedicated **"Live Tracking"** screen: a **map of Karachi** with a **moving dot per worker/vehicle**, updating in near-real-time (poll `/tracking/live` every ~3–5s; animate dots to new positions rather than snapping). This runs whenever field staff have the app + GPS on — it's an always-on operations view, not tied to any plan.

- **Dot styling by `subject_type`** (nurse/technician/driver/vehicle) — distinct icon/color, with a clear legend.
- **Stale handling:** a dot with `is_stale: true` (last ping older than `stale_after_sec`) is **greyed/faded** with a "last seen X ago" hint (`seconds_ago`). Fresh dots are solid. Don't present a 2-hour-old position as if it's live.
- **Click a dot → popup/side-panel** with the self-contained info the endpoint already returns: `name`, `employee_code`, `contact_number`, `subject_type`, and "last updated `seconds_ago`". No extra call needed.
- Consider a side list of all tracked staff (synced with the map) and a filter by type/availability.
- Empty state: "No workers are currently sharing location" when `positions` is empty.

### 8b. Solver Route map (MUST-HAVE, on Plan Detail)

On a solved plan, a prominent **map showing the routes the solver generated** — this is a headline visual. Data: `GET /v1/route-plans/{id}/map-data`.

- **Draw each driver's route as a polyline** from its `geometry` (real road-following path, `[lng, lat]` GeoJSON) — **one distinct color per driver route**. Fall back to connecting `points` with straight lines if `geometry` is null.
- **Depot marker** (distinct icon) + **order markers** — visually distinguish **served** (on a route) vs. **unserved** orders (`served: false`) — e.g. solid vs. hollow/red.
- **A well-formatted legend** is required: one entry per driver route showing color swatch + `driver_name` + `vehicle_plate` + `total_distance_m` (as km) + `total_time_sec` (as min). Plus legend entries for depot, served, and unserved markers.
- Interactions: click a route or its legend entry to highlight/isolate it; click an order marker to see which worker/route serves it. Auto-fit the map to the plan's bounds on load.
- Pair it with the driver-routes / worker-assignments tables (§8 Plan Detail) so operators can cross-read map ↔ table.

---

## 9. What the mobile app does (context only — you don't build or call this)

So you understand why data changes on its own: field workers (nurses/techs/drivers) use a separate Flutter app to receive their assigned jobs (after a plan is approved), share GPS during their shift, mark jobs `en_route`/`arrived`/`in_progress`/`completed`, and set themselves available/unavailable. All of that writes to the same backend. **Your console sees the effects by polling** — an order becomes `delivered`, a worker appears on the tracking map, someone goes unavailable on the roster. You never call the mobile endpoints (`/v1/mobile/*`); just poll the web endpoints in §4.7 and the order/dashboard endpoints to stay current.

---

## 10. Practical notes

- **Base URL**: configurable via env. Backend runs FastAPI; interactive API explorer at `/docs`.
- **Polling cadences** (suggested): dashboard ~10s, tracking ~3–5s, an in-progress plan uses SSE (no polling), plan lists on demand.
- **The SSE stream** is only live during a solve; if you open Plan Detail for an already-finished plan, skip the stream and render from `/diagnostics` + result endpoints.
- **Numbers**: distances are metres, times are seconds, currency is PKR. Format for humans (km, min, ₨).
- **Coordinates**: GeoJSON `[lng, lat]` in geometry payloads; individual markers give explicit `lat`/`lng` fields.
- **Don't invent endpoints** — everything you need is in §4 and `/openapi.json`. If something seems missing, flag it rather than faking it.

---

*System name: **Nightingale**. Build the admin/dispatcher console described above — robust, modular, industry-standard React — against this contract. The product owner reviews UX; you own the code.*
