# Nightingale — Data & Configuration Reference

> A snapshot of **what data the system stores** and **how the routing engine is currently
> tuned**. Part 1 walks through the database tables (from [src/db/models/](../src/db/models/))
> and explains what each column holds — focusing on the ones that aren't self-explanatory.
> Part 2 documents the ALNS solver configuration (from [src/core/config.py](../src/core/config.py)):
> fuel prices, penalties, thresholds, and pooling — with the values in effect as of the demo.
>
> **Config values are current as of 2026-07-14 (demo date).** They are defaults and can be
> overridden per solve via `RoutePlan.optimization_params`.

---

## Table of Contents

1. [Conventions](#1-conventions)
2. [Data Model](#2-data-model)
   - 2.1 [Common Columns (on almost every table)](#21-common-columns-on-almost-every-table)
   - 2.2 [Organization & People](#22-organization--people)
     - [companies](#companies) · [sys_users](#sys_users) · [users_companies](#users_companies) · [customers](#customers) · [employees](#employees) · [nurses](#nurses) · [technicians](#technicians) · [drivers](#drivers)
   - 2.3 [Places & Space](#23-places--space)
     - [locations](#locations) · [depots](#depots) · [zones](#zones) · [traffic_profiles](#traffic_profiles)
   - 2.4 [Fleet](#24-fleet)
     - [vehicles](#vehicles)
   - 2.5 [Work: Orders & Plans](#25-work-orders--plans)
     - [orders](#orders) · [route_plans](#route_plans)
   - 2.6 [Plan Output: the DARP-Hybrid Tables](#26-plan-output-the-darp-hybrid-tables)
     - [driver_routes](#driver_routes) · [driver_route_stops](#driver_route_stops) · [worker_assignments](#worker_assignments) · [worker_assignment_stops](#worker_assignment_stops)
   - 2.7 [Live Tracking & Mobile](#27-live-tracking--mobile)
     - [vehicle_position_events](#vehicle_position_events) · [worker_position_events](#worker_position_events) · [device_tokens](#device_tokens)
3. [ALNS Configuration](#3-alns-configuration)
   - 3.1 [Fuel Prices](#31-fuel-prices)
   - 3.2 [Penalties & Weights](#32-penalties--weights)
   - 3.3 [Thresholds](#33-thresholds)
   - 3.4 [Ride-Sharing / Pooling](#34-ride-sharing--pooling)
4. [Key Concepts Cheat-Sheet](#4-key-concepts-cheat-sheet)

---

## 1. Conventions

A few ideas recur across the whole schema. Understanding them once means most columns then
explain themselves.

- **H3 index (`h3_index`)** — Every place is tagged with an [Uber H3](https://h3geo.org/)
  hexagon ID: a short string like `"8a2a1072b59ffff"` that names a fixed hexagonal cell on the
  globe. It's the system's primary *spatial key*. Instead of comparing raw lat/lng, the system
  asks "which hex is this in?" so it can group nearby points, look up traffic, and pool riders.
  Resolutions used: **res-9 (~174 m hex)** on individual points (locations, positions), and
  **res-8 (~460 m hex)** for zone/traffic and pooling ("same area"). You climb from a res-9 hex
  to its res-8 parent with one H3 call.

- **Soft references (`worker_id` + `worker_type`)** — A nurse and a technician live in two
  different tables. Where a row needs to point at "a worker" that could be either, it stores an
  integer `worker_id` plus a `worker_type` discriminator (`nurse` / `technician`) instead of a
  real foreign key — because a single FK can't target two tables. The pair together identifies
  the actual row.

- **`service_type` discriminator** — A company runs *either* nurses *or* technicians, never
  both. That single field on `companies` decides which worker tables, which skill set, and which
  order-skill column apply throughout.

- **Enum columns** — Many status/type fields are constrained enums (defined in
  [src/core/enums.py](../src/core/enums.py)). Their allowed values are listed inline below.

---

## 2. Data Model

### 2.1 Common Columns (on almost every table)

To avoid repeating them on every table, these audit columns appear on nearly all models and are
**omitted from the per-table lists below** unless a table does something unusual:

| Column        | Meaning                                                                 |
|---------------|-------------------------------------------------------------------------|
| `id`          | Auto-incrementing integer primary key (unless noted otherwise).         |
| `created_at`  | Timestamp the row was first inserted (server default = now).            |
| `created_by`  | ID of the user who created the row.                                     |
| `updated_at`  | Timestamp of the last update (auto-set on change).                      |
| `updated_by`  | ID of the user who last updated the row.                                |
| `deleted_at`  | When the row was soft-deleted (null = live). Rows are hidden, not gone. |
| `deleted_by`  | ID of the user who soft-deleted the row.                                |
| `is_deleted`  | Boolean soft-delete flag (present on some tables instead of/alongside `deleted_at`). |

> **Soft delete:** the system marks rows deleted rather than physically removing them, so history
> and audit trails survive.

---

### 2.2 Organization & People

#### companies

The top-level tenant. Everything else hangs off a company.

| Column                   | Meaning                                                                 |
|--------------------------|-------------------------------------------------------------------------|
| `name`                   | Company name.                                                            |
| `contact_number`, `contact_email` | Primary contact details.                                       |
| `timezone`               | IANA timezone for scheduling (default `Asia/Karachi`).                  |
| `service_type`           | **Discriminator** — `nurse` or `technician`. Decides the entire worker/skill flavour for this company (see [Conventions](#1-conventions)). |
| `head_office_location_id`| FK to the company's head-office `locations` row.                        |

#### sys_users

Back-office / admin console login accounts (dispatchers, admins) — distinct from field workers.

| Column                    | Meaning                                                        |
|---------------------------|----------------------------------------------------------------|
| `username`                | Login handle (unique).                                          |
| `password_hash`           | Hashed password (never plaintext).                             |
| `role`                    | Free-text role string (RBAC is not yet formalized).           |
| `primary_contact_number`, `primary_contact_email` | Contact details.                      |

#### users_companies

Join table linking `sys_users` ↔ `companies` (a user can be tied to companies). Its primary key
is the `(user_id, company_id)` pair — no surrogate `id`.

#### customers

The company's end customers, whose locations orders are serviced at.

| Column         | Meaning                                                    |
|----------------|-------------------------------------------------------------|
| `name`         | Customer name.                                              |
| `company_id`   | Owning company.                                             |
| `location_id`  | FK to this customer's `locations` row (their address/hex).  |
| `contact_email`, `contact_phone` | Contact details.                          |

#### employees

The **person** record for any field staff member. A worker's *identity* (name, contact, login,
shift, availability) lives here; their *role-specific* data (skills, ratings) lives in the
`nurses` / `technicians` / `drivers` tables that point back at this row.

| Column                | Meaning                                                                          |
|-----------------------|-----------------------------------------------------------------------------------|
| `name`, `contact_number`, `contact_email` | Personal details.                                     |
| `cnic`                | National ID number (Pakistan CNIC).                                               |
| `company_id`          | Employing company.                                                                |
| `shift_start`, `shift_end` | Daily working window (time-of-day). Used by the solver as the worker's availability window. |
| `operational_status`  | `active` / `suspended` / `inactive`. **Note:** "suspended" currently doubles as "self-marked unavailable" — a known ambiguity flagged in the future-improvements doc. |
| `username`, `password_hash` | **Mobile login** — field workers authenticate on the app as an Employee. |
| `unavailable_reason`  | Free text a worker gives when marking themselves unavailable (admin sees who + why). |
| `status_changed_at`   | When `operational_status` last changed.                                          |

#### nurses

Role record for a nurse, linked 1:1 to an `employees` row.

| Column              | Meaning                                                                        |
|---------------------|---------------------------------------------------------------------------------|
| `employee_id`       | FK back to the person in `employees`.                                           |
| `orders_completed`  | Lifetime count of completed jobs.                                               |
| `rating`            | Performance rating (0.0 default; rating algorithm not yet implemented).         |
| `skills`            | **Array** of clinical skills this nurse holds. Values: `iv_administration`, `phlebotomy`, `wound_care`, `triage`, `ventilator_management`, `dialysis`. Matched against an order's `required_nurse_skills`. |
| `operational_status`| `active` / `suspended` / `inactive`.                                            |

#### technicians

Role record for a technician, linked 1:1 to an `employees` row. Same shape as `nurses` but with
a different skill vocabulary.

| Column              | Meaning                                                                        |
|---------------------|---------------------------------------------------------------------------------|
| `employee_id`       | FK back to the person in `employees`.                                           |
| `orders_completed`  | Lifetime completed jobs.                                                        |
| `rating`            | Performance rating (0.0 default).                                               |
| `skills`            | **Array** of technical skills. Values: `network_setup`, `hardware_installation`, `cable_management`, `system_configuration`. Matched against an order's `required_tech_skills`. |
| `operational_status`| `active` / `suspended` / `inactive`.                                            |

#### drivers

The person who drives a vehicle and shuttles workers between jobs.

| Column                  | Meaning                                                                     |
|-------------------------|------------------------------------------------------------------------------|
| `company_id`            | Employing company.                                                           |
| `employee_id`           | FK to the underlying `employees` person (nullable).                          |
| `vehicle_id`            | The vehicle currently assigned to this driver.                              |
| `drivers_license_number`| License number.                                                             |
| `orders_completed`      | Lifetime completed trips.                                                    |
| `kms_driven`            | Lifetime distance driven.                                                    |
| `rating`                | Performance rating (0.0 default).                                           |
| `skills`                | **Array** of `VehicleType` values the driver is qualified to drive: `bike`, `car`, `van`, `truck`. |
| `operational_status`    | `active` / `suspended` / `inactive`.                                        |

---

### 2.3 Places & Space

#### locations

A physical point on the map. Referenced by customers, depots, orders, and route stops.

| Column         | Meaning                                                                                 |
|----------------|------------------------------------------------------------------------------------------|
| `type`         | `company_head_office` / `company_depot` / `customer_location` (nullable).                |
| `lat`, `lng`   | Raw coordinates.                                                                          |
| `h3_index`     | **Res-9 H3 hex** for this point (indexed) — the spatial key used everywhere. See [Conventions](#1-conventions). |
| `address_text` | Human-readable address (optional).                                                       |

#### depots

A company site where vehicles are based and routes begin/end. For the demo, plans assume a
single depot start.

| Column               | Meaning                                                    |
|----------------------|-------------------------------------------------------------|
| `company_id`         | Owning company.                                             |
| `name`               | Depot name.                                                 |
| `location_id`        | FK to the depot's `locations` row.                         |
| `operational_status` | `active` / `suspended` / `inactive`.                       |

#### zones

Master table of the H3 hexagons the system cares about. **The `h3_index` *is* the primary key** —
there is no separate `id`.

| Column                    | Meaning                                                                     |
|---------------------------|------------------------------------------------------------------------------|
| `h3_index`                | H3 hex ID — the primary key.                                                 |
| `resolution`              | H3 resolution of this hex (res-8 hexes are stored here for zone profiles).   |
| `center_lat`, `center_lng`| Geographic center of the hex.                                               |
| `city`                    | City the hex belongs to.                                                     |
| `label`                   | Human-readable district name, e.g. "Clifton", "Saddar", "Korangi".          |

#### traffic_profiles

Time-of-day traffic multipliers per zone. This is how the router makes travel time depend on
*when* you drive, not just distance — a trip through a busy hex at rush hour costs more time than
the same trip at midnight.

| Column                   | Meaning                                                                        |
|--------------------------|---------------------------------------------------------------------------------|
| `h3_index`               | FK to `zones` — which hex this profile applies to.                             |
| `day_type`               | `weekday` / `friday` / `saturday` / `sunday` / `public_holiday`.                |
| `hour_start`, `hour_end` | The hour band (0–23 inclusive) this multiplier covers.                         |
| `multiplier`             | Travel-time multiplier for that hex/day/hour (e.g. `1.4` = 40 % slower than baseline). |
| `road_type`              | Optional road classification the profile applies to.                           |
| `source`                 | `synthetic` (hand-authored for the demo) or `learned` (from real data, future).|

> Indexed on `(h3_index, day_type, hour_start, hour_end)` for instant "given a hex + day + hour,
> get the multiplier" lookups.

---

### 2.4 Fleet

#### vehicles

A vehicle in the fleet. In the current model a vehicle is a **transport for workers** — it does
not yet carry tools/equipment with capacity constraints.

| Column                    | Meaning                                                                       |
|---------------------------|--------------------------------------------------------------------------------|
| `company_id`, `depot_id`  | Owning company and home depot.                                                 |
| `license_plate`           | Plate number.                                                                  |
| `type`                    | `bike` / `car` / `van` / `truck`.                                              |
| `model`, `color`, `engine_cc` | Descriptive attributes.                                                    |
| `max_weight_kg`, `max_volume_m3` | Cargo capacity limits (reserved for future equipment-carrying).         |
| `seating_capacity`        | How many riders (workers) it can carry — **the cap on ride-pooling** (see [pooling](#34-ride-sharing--pooling)). |
| `avg_speed_kmh`           | Assumed average speed (default 40) when estimating travel time.               |
| `fuel_type`               | `petrol` / `diesel` / `electric` / `cng` (default `petrol`). Picks which price applies from [Fuel Prices](#31-fuel-prices). |
| `fuel_average`            | Fuel consumption rate — litres (or kWh) per km. Used in the fuel-cost formula: `distance_km × fuel_average × price`. |
| `monthly_maintenance_cost`| Fixed upkeep cost (not yet used in the objective).                            |
| `operational_status`      | `active` / `suspended` / `inactive`.                                          |

---

### 2.5 Work: Orders & Plans

#### orders

A single job to be serviced (a home nursing visit or a technician callout). This is the demand
the solver schedules.

| Column                    | Meaning                                                                        |
|---------------------------|---------------------------------------------------------------------------------|
| `name`                    | Optional label for the order.                                                  |
| `company_id`, `customer_id` | Owning company and the customer being served.                                |
| `location_id`             | Where the service happens. **Null means it starts from the depot.**            |
| `weight_kg`, `volume_m3`  | Cargo size (reserved for the future equipment-carrying model).                 |
| `required_nurse_skills`   | **Array** of nurse skills the order needs — populated only for nurse-companies. |
| `required_tech_skills`    | **Array** of technician skills the order needs — populated only for technician-companies. Only one of these two is ever set, per the company's `service_type`. |
| `service_date`            | **The calendar day this order is serviced. Authoritative for scheduling** — a route plan solves exactly one `service_date`'s orders (the solver is single-day by design). |
| `timewindow_start`, `timewindow_end` | The *within-day* window the service must fall in. `service_date` picks the day; these refine the time. Lateness beyond this window incurs the tardiness penalty. |
| `service_duration_min`    | Minutes the worker spends on-site. Falls back to the config default (`DEFAULT_SERVICE_DURATION_MIN`, 30 min) when null. |
| `priority`                | `low` / `normal` / `high` / `urgent` (default `normal`).                       |
| `status`                  | `pending` / `assigned` / `in_transit` / `delivered` / `failed` (default `pending`). |
| `notes`                   | Free-text notes.                                                               |

#### route_plans

One optimization run for one depot on one day — the container for a solver result.

| Column                  | Meaning                                                                          |
|-------------------------|-----------------------------------------------------------------------------------|
| `company_id`, `depot_id`| Which company/depot this plan is for.                                             |
| `name`                  | Optional plan name.                                                              |
| `planned_date`          | The service day this plan covers.                                                |
| `status`                | `draft` / `optimizing` / `ready` / `dispatched` / `completed` / `failed`.        |
| `optimization_params`   | **JSON snapshot of the solver config used for this run** — any config default (penalties, pooling, ALNS loop settings, `max_vehicles`, etc.) can be overridden here per plan. |
| `total_orders`          | Orders included in the plan.                                                     |
| `total_routes`          | Number of driver routes produced.                                               |
| `total_unserved`        | Orders the solver could not serve.                                              |
| `objective_value`       | Final objective (total cost) of the winning solution — lower is better.          |
| `solver_diagnostics`    | **JSON telemetry for the demo dashboard**: per-iteration objective trace, operator counts, cost breakdown, runtime, unserved reasons (built by [alns/persistence.py](../src/services/alns/persistence.py)). |
| `optimized_at`          | When optimization finished.                                                      |

---

### 2.6 Plan Output: the DARP-Hybrid Tables

The solver output is split into two sides of a Dial-A-Ride-style problem: **drivers move**,
**workers serve**. Four tables express this.

```
route_plans
    │
    ├── driver_routes            (the MOVER side — one driver+vehicle's shuttle path)
    │       └── driver_route_stops   (each depot / dropoff / pickup leg, in order)
    │
    └── worker_assignments       (the SERVICE side — one worker's day of jobs)
            └── worker_assignment_stops  (each order served, in order)
                    │
                    └── links back to the driver_route_stops that
                        dropped the worker off and picked them up
```

#### driver_routes

One driver+vehicle's physical route for a plan — the "shuttle" path that moves workers around.

| Column                          | Meaning                                                              |
|---------------------------------|----------------------------------------------------------------------|
| `plan_id`, `vehicle_id`, `driver_id` | The plan, vehicle, and driver this route belongs to.            |
| `status`                        | `pending` / `active` / `completed` / `cancelled`.                    |
| `total_distance_m`, `total_time_sec` | Totals for the whole route.                                     |
| `total_fuel_cost`, `estimated_cost` | Computed fuel cost and overall estimated cost of the route.     |
| `departure_time`                | When the driver leaves the depot.                                    |
| `geometry`                      | The full drawn path as a **GeoJSON LineString**, for map rendering.  |

#### driver_route_stops

One leg of a driver's route: arriving somewhere to drop off / pick up a worker, or a depot
start/end. A single stop can serve multiple workers (a van dropping two nurses at nearby orders).

| Column                  | Meaning                                                                        |
|-------------------------|---------------------------------------------------------------------------------|
| `driver_route_id`       | The route this stop is part of.                                                |
| `location_id`           | Where the stop is.                                                             |
| `sequence_number`       | Order of this stop within the route (stops are read in this order).           |
| `stop_type`             | `depot_start` / `dropoff` / `pickup` / `depot_end` (also `delivery` in the enum). |
| `eta`, `etd`            | Estimated time of arrival / departure (planned).                              |
| `distance_from_prev_m`, `time_from_prev_sec` | Leg distance/time from the previous stop.                |
| `arrived_at`, `departed_at` | Actual times, filled in real time when live tracking is active.           |

#### worker_assignments

One nurse/technician's service day within a plan — the ordered set of orders that worker serves.
The worker doesn't drive; they're shuttled between jobs by drivers.

| Column        | Meaning                                                                                  |
|---------------|-------------------------------------------------------------------------------------------|
| `plan_id`     | The plan this belongs to.                                                                 |
| `worker_id`   | **Soft reference** to the worker — points into `nurses` *or* `technicians`.               |
| `worker_type` | Discriminator (`nurse` / `technician`) that says which table `worker_id` refers to.       |

#### worker_assignment_stops

One order served by one worker, in sequence within that worker's day. This is where the service
side connects to the shuttle side, and where the mobile app reports execution.

| Column                          | Meaning                                                              |
|---------------------------------|----------------------------------------------------------------------|
| `worker_assignment_id`          | Which worker's day this stop belongs to.                            |
| `order_id`                      | The order being served.                                             |
| `sequence_number`               | Order of this job in the worker's day.                             |
| `service_start_estimated`, `service_end_estimated` | Planned on-site start/end times.                |
| `dropoff_stop_id`               | The `driver_route_stops` leg that **dropped the worker off** here (nullable — a worker taken straight to a consecutive order may have no distinct dropoff). |
| `pickup_stop_id`                | The `driver_route_stops` leg that **picked the worker up** afterward (nullable). |
| `stop_status`                   | **Mobile execution state** the worker reports: `pending` / `en_route` / `arrived` / `in_progress` / `completed` / `failed`. |
| `actual_service_start`, `actual_service_end` | Real on-site times reported from the app.             |
| `completion_notes`              | Free-text notes the worker leaves on completion.                    |

---

### 2.7 Live Tracking & Mobile

#### vehicle_position_events

Append-only GPS log for vehicles. **Empty before a trip starts;** rows are inserted while live
tracking is active and can trigger re-routing.

| Column            | Meaning                                                                     |
|-------------------|------------------------------------------------------------------------------|
| `vehicle_id`      | The vehicle being tracked.                                                   |
| `driver_route_id` | The active route this ping belongs to (nullable).                          |
| `recorded_at`     | When the position was captured.                                            |
| `lat`, `lng`      | Coordinates.                                                               |
| `h3_index`        | Res-9 hex of the ping (indexed).                                           |
| `speed_kmh`       | Speed at capture.                                                          |
| `source`          | `gps` / `simulated` / `manual`.                                           |

> Indexed on `(vehicle_id, recorded_at)` to fetch a vehicle's recent track quickly.

#### worker_position_events

Append-only GPS log for **any field worker** (nurse / technician / driver). Vehicle events only
cover drivers who have a vehicle; nurses and techs share location during a shift too, and those
pings land here. A driver's app may write to both tables.

| Column        | Meaning                                                                          |
|---------------|-----------------------------------------------------------------------------------|
| `worker_id` + `worker_type` | **Soft reference** identifying which worker (nurse/technician/driver). |
| `recorded_at` | When the position was captured.                                                  |
| `lat`, `lng`  | Coordinates.                                                                     |
| `h3_index`    | Res-9 hex of the ping (indexed, nullable).                                       |
| `accuracy_m`  | GPS accuracy radius in meters.                                                   |
| `source`      | `gps` / `simulated` / `manual`.                                                 |

> Indexed on `(worker_type, worker_id, recorded_at)`.

#### device_tokens

Push-notification targets. Each row is one Firebase Cloud Messaging (FCM) token for a worker's
device. A worker may have several devices; the app registers/refreshes its token on every login
(tokens rotate), and the backend pushes job alerts to a worker's active tokens on plan approval.

| Column        | Meaning                                                       |
|---------------|---------------------------------------------------------------|
| `employee_id` | The worker (Employee) who owns the device.                    |
| `token`       | The FCM device token.                                         |
| `platform`    | `android` / `ios` (default `android`).                        |
| `active`      | Whether this token is still valid to send to.                 |
| `last_seen`   | When the device last checked in.                              |

---

## 3. ALNS Configuration

All values below come from [src/core/config.py](../src/core/config.py) and are consumed by the
solver's cost function in [src/services/alns/cost.py](../src/services/alns/cost.py). **These are
the demo-time defaults (2026-07-14).** Any of them can be overridden for a single run through the
plan's `optimization_params`.

### 3.1 Fuel Prices

`FUEL_PRICES` — price per litre (petrol / diesel / CNG) or per kWh (electric), in **PKR**. The
fuel-cost component computes `distance_km × vehicle.fuel_average × price`, picking the price by
the vehicle's `fuel_type`.

| Fuel type  | Price (PKR) | Unit      |
|------------|-------------|-----------|
| Petrol     | 280.0       | per litre |
| Diesel     | 290.0       | per litre |
| CNG        | 190.0       | per litre |
| Electric   | 60.0        | per kWh   |

### 3.2 Penalties & Weights

`ALNS_PENALTIES` — the objective function is a sum of costs; these weights decide how strongly
the solver avoids each kind of undesirable outcome. Bigger number = the solver tries harder to
avoid it. All are **defaults** and overridable per run.

| Penalty key           | Value  | What it penalizes                                                                                 |
|-----------------------|--------|---------------------------------------------------------------------------------------------------|
| `tardiness_per_min`   | 2.0    | Each minute an order is served **late**, past its time window.                                     |
| `overtime_per_min`    | 3.0    | Each minute a worker works **beyond their shift end**.                                             |
| `skill_violation`     | 200.0  | Assigning a worker an order they lack the skill for. A safety net — should be near-impossible, since insertion already hard-filters on skills. |
| `unserved_order`      | 500.0  | Each order left **unassigned**. High, so the solver serves orders whenever it feasibly can.        |
| `excess_wait_per_min` | 5.0    | Each minute a worker waits on a driver pickup **beyond the free threshold** (see below).           |
| `shuttle_infeasible`  | 300.0  | Flat penalty when a dropoff/pickup can't be feasibly served within the shuttle-infeasible window by the nearest driver. |

Related default:

| Key                            | Value | Meaning                                                                 |
|--------------------------------|-------|-------------------------------------------------------------------------|
| `DEFAULT_SERVICE_DURATION_MIN` | 30    | Fallback on-site service time (minutes) when an order has no `service_duration_min`. |

### 3.3 Thresholds

The two "grace windows" that decide when the wait and shuttle penalties above kick in:

| Setting                        | Value        | Meaning                                                                                    |
|--------------------------------|--------------|---------------------------------------------------------------------------------------------|
| `EXCESS_WAIT_THRESHOLD_MIN`    | 15 min       | A worker may wait this long for a pickup **for free**; only minutes beyond this trigger `excess_wait_per_min`. |
| `SHUTTLE_INFEASIBLE_AFTER_MIN` | 45 min       | If the nearest driver can't reach a pickup/dropoff within this delay, the leg is treated as infeasible and `shuttle_infeasible` fires. |

### 3.4 Ride-Sharing / Pooling

`POOL_*` — this is what makes the shuttle a true dial-a-ride: multiple workers heading to nearby
jobs at similar times can **share one driver leg** instead of each needing a separate trip.

| Setting              | Value | Meaning                                                                                             |
|----------------------|-------|-----------------------------------------------------------------------------------------------------|
| `POOL_ENABLED`       | `True`| Master switch for ride-pooling.                                                                     |
| `POOL_WINDOW_MIN`    | 60    | Workers whose trips fall within this many minutes of each other are eligible to pool together.      |
| `POOL_H3_RESOLUTION` | 8     | The H3 resolution that defines "same area" — res-8 (~460 m neighbourhood). Workers heading to orders in the same res-8 hex can pool. |

> Pooling is additionally capped by the vehicle's `seating_capacity` — you can't pool more riders
> than the van has seats.

---

## 4. Key Concepts Cheat-Sheet

| Term                    | One-liner                                                                                   |
|-------------------------|----------------------------------------------------------------------------------------------|
| **H3 index**            | A hexagon ID naming a cell on the map; the system's spatial key. Res-9 for points, res-8 for zones/pooling. |
| **`service_type`**      | Company-level switch: this company runs *nurses* or *technicians*, never both.               |
| **Soft reference**      | `worker_id` + `worker_type` pointing into one of two worker tables (no single FK possible).   |
| **DARP-hybrid**         | Drivers *move* (driver_routes), workers *serve* (worker_assignments); the two link through stops. |
| **Pooling**             | Several workers sharing one driver leg when they're near each other, in time and in space.    |
| **Soft delete**         | Rows are flagged deleted (`deleted_at` / `is_deleted`), never physically removed.             |
| **`optimization_params`** | Per-plan JSON that can override any solver config default for that one run.                 |

---

*Data snapshot describes the schema under [src/db/models/](../src/db/models/); config values are
current as of the 2026-07-14 demo and live in [src/core/config.py](../src/core/config.py). Update
this document if either changes.*
