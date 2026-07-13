# Backend Build Plan — API, Auth, CRUD, Mobile & Real-time

**Purpose:** Bring the system from "ALNS solver + route-plan endpoints" to a full backend that a web admin frontend and a Flutter field-ops mobile app can both run against. This document is the spec for that build and the review artifact before any code is written.

**Status:** PLAN — awaiting no further decisions. Ready to execute in the build order at the end.

---

## 0. Two populations, two auth paths (foundational)

The system has **two distinct user populations** that log in separately:

| Population | Table | Logs into | Identity returned | Purpose |
|---|---|---|---|---|
| **System operators** (admin/dispatcher) | `SysUsers` | **Web** frontend | `user_id`, `company_id` | Enter orders/fleet/worker info, view/edit everything, create & approve schedules. Every audit `created_by`/`updated_by` is a SysUser id. |
| **Field workers** (nurse/tech/driver) | `Employee` (+ domain row in `drivers`/`nurses`/`technicians`) | **Mobile** app | `employee_id`, `company_id`, `role` | Receive assignments, share GPS, mark jobs done, set availability. |

**Consequences:**
- `Employee` gains `username` + `password_hash` (it currently has no login capability).
- Web login: `POST /v1/auth/login` → authenticates a `SysUser`.
- Mobile login: `POST /v1/mobile/auth/login` → authenticates an `Employee`; `role` derived from which domain table (`drivers`/`nurses`/`technicians`) holds their row.
- Two dependencies: `get_current_user` (web → SysUser) and `get_current_worker` (mobile → Employee). Both resolve `company_id` from the identity so **no endpoint takes `company_id` as a request param** — it comes from auth.

**Auth mechanism (both paths):** bcrypt password verify + an hmac-signed stdlib token (no JWT lib). Token encodes the subject id + type (`sysuser`/`employee`) + company_id, signed with `SECRET_KEY`. `get_current_*` verifies signature and loads the subject. No expiry yet (documented gap; mobile plan §12 also flags this — a 401 story comes later).

---

## 1. New & modified enums (`src/core/enums.py`)

```python
class WorkerStopStatus(str, Enum):   # per-order execution state on WorkerAssignmentStop
    pending     = "pending"
    en_route    = "en_route"
    arrived     = "arrived"
    in_progress = "in_progress"
    completed   = "completed"
    failed      = "failed"

class DevicePlatform(str, Enum):
    android = "android"
    ios     = "ios"
```

Existing enums reused: `OrderStatus` (rollup target), `OperationalStatus` (availability: active↔suspended), `ServiceType` (worker_type), `PositionSource` (GPS source), `PlanStatus` (adds nothing — `dispatched` already exists for approve).

---

## 2. DB model changes (+ Alembic migrations)

### New models

**`DeviceToken`** — FCM push targets (a user may have several devices)
```
id, user_id (FK sys_users? or employee?), token, platform (DevicePlatform),
last_seen, active (bool), + audit cols
```
> NOTE: field workers are the push recipients (job alerts), so `user_id` here references **Employee**, not SysUsers. Named `employee_id`.

**`WorkerPositionEvent`** — any field worker's GPS log (nurses/techs aren't vehicle-keyed)
```
id, worker_id, worker_type (ServiceType), lat, lng, h3_index, accuracy,
recorded_at, source (PositionSource), + minimal audit
```
Append-only, mirrors `VehiclePositionEvent` but keyed by worker. `VehiclePositionEvent` stays as-is (driver/vehicle + ALNS tracking).

### Modified models

**`Employee`** +=
```
username (unique, nullable until set), password_hash (nullable),   # mobile login
unavailable_reason (nullable str), status_changed_at (datetime)    # availability
```
Employee is the **availability source of truth** (shared identity behind nurse/tech/driver). `operational_status` already exists here.

**`WorkerAssignmentStop`** +=
```
actual_service_start (datetime, nullable), actual_service_end (datetime, nullable),
stop_status (WorkerStopStatus, default pending), completion_notes (text, nullable)
```
Mobile "mark complete/status" writes here. Completing a stop **rolls up** `Order.status = delivered`.

No change to `Order` (completion is a rollup to existing `status`).

---

## 3. Repositories (`src/db/repositories/`, one per model)

All DB access for new/CRUD endpoints goes through a repo (ALNS-service direct queries stay as they are, per your call). Each mirrors its model filename:

`sys_users.py`, `employee.py` (both auth + CRUD), `company.py`, `customer.py`, `order.py`, `vehicle.py`, `driver.py`, `nurse.py`, `technician.py`, `depot.py`, `route_plan.py`, `device_token.py`, `worker_position.py`, `vehicle_position.py`, `worker_assignment.py` (mobile read side), `location.py` (shared location upsert used by customer/depot/order writes).

Repo convention: constructed with a `Session`; methods return models or None; **soft-delete** via existing `deleted_at`/`deleted_by`; every list method is **company-scoped** (takes company_id from the caller, never trusts the client).

---

## 4. Exceptions (`src/exceptions/`, one file per router domain)

Typed `HTTPException` subclasses, each with a stable `error_code` string + human `message`, so the frontend can branch on `error_code` and show `message`. Files:

- `auth.py` — `InvalidCredentials` (401), `InvalidToken` (401), `InactiveAccount` (403)
- `common.py` — `EntityNotFound` (404), `CrossCompanyAccess` (403), `DuplicateEntity` (409), `ValidationFailed` (400)
- `orders.py` — `OrderNotFound`, `OrderNotServable`, `OrdersSpanMultipleDates`, `NoServableOrders`
- `route_plans.py` — `PlanNotFound`, `PlanNotReady`, `PlanAlreadyDispatched`, `NoDiagnostics`
- `mobile.py` — `NotAssignedToYou` (403), `StopAlreadyCompleted` (409), `WorkerNotFound`

Example shape:
```python
class OrderNotFound(HTTPException):
    def __init__(self, order_id: int):
        super().__init__(status_code=404,
            detail={"error_code": "order_not_found",
                    "message": f"Order {order_id} does not exist."})
```

---

## 5. Schemas (`src/schemas/`, one file per router)

Detailed, frontend-friendly Pydantic response models (Claude Design consumes these). One file per router: `auth.py`, `company.py`, `customer.py`, `order.py`, `vehicle.py`, `driver.py`, `worker.py` (nurse/tech unified), `employee.py`, `depot.py`, `route_plan.py` (exists — extend), `mobile.py`, `tracking.py`, `dashboard.py`, `meta.py`.

**GET responses are rich** — e.g. an Order lists its customer name + contact + location address, not just `customer_id`; a Driver lists its employee name/contact + vehicle plate, not just FKs. This is so the frontend can render useful views without N+1 follow-up calls.

---

## 6. Routers (`src/api/v1/`)

### 6.1 Foundation
- **`deps.py`** — `get_current_user` (web/SysUser), `get_current_worker` (mobile/Employee). Both yield an identity object with `company_id`.
- **`auth.py`** — `POST /v1/auth/login` (SysUser), `POST /v1/auth/logout`, `GET /v1/auth/me`.

### 6.2 CRUD (full: list / get / create / update / soft-delete), web, company-scoped via auth
- `companies.py` — `GET /v1/company` (own), `PUT /v1/company` (no create/delete — tenant-fixed)
- `customers.py` — full CRUD; GET includes location + order count
- `orders.py` — **extend existing**; full CRUD; GET includes customer + location + required skills + service_date/status; the ALNS selection GET (`/v1/orders`) already exists → refactor to auth-scoped
- `vehicles.py` — full CRUD; GET includes depot name + assigned driver
- `drivers.py` — full CRUD; GET includes employee name/contact + vehicle + availability
- `workers.py` — full CRUD for nurse/tech (by company `service_type`); GET includes employee name/contact + skills + availability
- `employees.py` — full CRUD; underlies workers; GET includes shift + operational_status + which domain role
- `depots.py` — full CRUD; GET includes location
- `route_plans.py` — **extend existing**: `GET /v1/route-plans` (list/history), `GET /{id}` (exists), `DELETE /{id}` (draft only), `POST /{id}/approve`

### 6.3 RoutePlan lifecycle
- **`POST /v1/route-plans/{id}/approve`** — plan `ready → dispatched`; its orders → `assigned`; each `WorkerAssignmentStop.stop_status = pending`; notify assigned workers via FCM. Plan becomes read-only. **Workers are NOT locked** — a worker can hold many jobs across plans, each with its own `stop_status`.

### 6.4 Mobile (backend-facing only — the app never talks to the web frontend)
Prefix `/v1/mobile`, authed via `get_current_worker`:
- `POST /auth/login` (Employee), `POST /auth/logout`, `POST /auth/fcm-token` (register DeviceToken)
- `GET /my-assignments?date=` — this worker's assigned stops for a date: order info, location, ETA/service window, sequence, current stop_status, route_polyline (from the worker's driver-route geometry)
- `POST /orders/{stop_id}/status` — set stop_status (en_route/arrived/in_progress); writes actuals
- `POST /orders/{stop_id}/complete` — stop_status=completed + notes + actual_service_end; **rolls up Order.status=delivered**
- `POST /position` — batch GPS → `WorkerPositionEvent` (+ `VehiclePositionEvent` if the worker is a driver with a vehicle)
- `POST /availability` — set available/unavailable + reason → Employee.operational_status + unavailable_reason + status_changed_at
- `GET /availability/me`

### 6.5 Web real-time (polling now; SSE noted as future)
- **`tracking.py`** — `GET /v1/tracking/live` — latest position per active worker/vehicle for the company (map markers). *(SSE upgrade = future TODO.)*
- **`dashboard.py`** — `GET /v1/dashboard/today` — today's ops: plans, orders by status, active/available workers, completion %.
- **Availability roster** — `GET /v1/workers/availability` — every worker with name, contact, role, operational_status, unavailable_reason, since. (Admin sees who's un/available & why.)

### 6.6 Meta
- **`meta.py`** — `GET /v1/meta/enums` — all enum values (skills per service_type, statuses, priorities, vehicle/fuel types) so the frontend renders selects/labels without hardcoding.

---

## 7. Cross-cutting changes to existing code

- **Refactor** `/v1/orders` and `/v1/route-plans` (POST) to drop the explicit `company_id` param and derive it from `get_current_user`.
- **ALNS loader fix** — `load_problem_data` filters workers to `operational_status = active` (exclude self-suspended workers from NEW plans; existing assignments untouched).
- **`SysUsers.__repr__` bug** — references nonexistent `self.company_id`; fix while touching the model.

---

## 8. FCM (real integration, with a stub fallback)

Build `DeviceToken` storage + a `notify_workers(employee_ids, title, body, data)` service now. The real FCM HTTP v1 send needs a Firebase **service-account JSON** + project id. **When the build reaches the notify implementation, STOP and request those credentials.** If not available then, ship the stub (`notify` logs "would push to tokens [...]" + records intent) and return to it — no other code changes when the real send drops in.

---

## 9. Seeding

Extend/adjust the synthetic generator (or a new demo-seed script) to create: 2 SysUsers (user1→company1 nurse, user2→company2 tech) with known passwords + UserCompany links; Employees with usernames/passwords for mobile login; and the existing fleet/orders. So both web and mobile logins work out of the box for the demo.

---

## 10. Build order (dependency-respecting)

1. **Enums + models + migrations** (WorkerStopStatus, DevicePlatform; DeviceToken, WorkerPositionEvent; Employee/WorkerAssignmentStop cols)
2. **Auth foundation** — `deps.py`, `auth.py`, exceptions/auth, schemas/auth, sys_users + employee repos, token util, SysUser/Employee seeding
3. **Refactor existing** `/orders` + `/route-plans` to auth-scoping; ALNS loader suspend-filter
4. **Repositories** for all CRUD entities
5. **CRUD routers** (+ schemas + exceptions) — companies, customers, orders, vehicles, drivers, workers, employees, depots
6. **RoutePlan lifecycle** — list/get/delete + approve (+ FCM notify hook; stop for Firebase creds)
7. **Mobile router** — worker auth, my-assignments, status/complete, position, availability
8. **Web real-time** — tracking, dashboard, availability roster, meta
9. **Seed + end-to-end test** every router (web login → CRUD → create plan → approve → mobile login → my-assignments → complete → dashboard reflects it)

---

## 11. What Claude Design gets (separate doc, written after this is built)

A frontend-facing md: backend overview, every endpoint with **purpose + expected UX flow**, the enums (what each value means/looks like), the exceptions (error_code → what to tell the user), and the schemas (field-by-field). Plus the OpenAPI/Swagger at `/docs` as the machine-readable companion. UX flows spelled out where non-obvious (order-selection → solve → approve; live tracking; the availability roster; today's dashboard).
```
```
