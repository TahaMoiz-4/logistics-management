# Nightingale — ALNS Routing Engine: Review & Roadmap

> **Purpose.** A discussion document for the algorithm review meeting. Part I explains
> what the solver actually does today and why it's built that way. Part II is the honest
> list of what it doesn't do, where it can go wrong, and the traps for anyone editing it.
> Part III is a ranked, sized roadmap for where we take it next.
>
>
> Code lives under [src/services/alns/](../src/services/alns/). Companion documents:
> [Future Improvements & Concerns.md](Future%20Improvements%20&%20Concerns.md),
> [Backend Architecture.md](Backend%20Architecture.md).

---

## Table of Contents

**Part I — How it works**
1. [The problem in plain terms](#1-the-problem-in-plain-terms)
2. [Why ALNS, and how ALNS works](#2-why-alns-and-how-alns-works)
   — including [what an "operator" actually is](#what-an-operator-actually-is) *(start here if the term is new)*
3. [Our specific design: worker-centric state, derived driver routes](#3-our-specific-design-worker-centric-state-derived-driver-routes)
4. [The search loop, operator by operator](#4-the-search-loop-operator-by-operator)
5. [The objective function](#5-the-objective-function)

**Part II — Inputs, knobs, and where it breaks**

6. [Inputs and how an instance is built](#6-inputs-and-how-an-instance-is-built)
7. [Constraints: hard, soft, and absent](#7-constraints-hard-soft-and-absent)
8. [Every tunable parameter](#8-every-tunable-parameter)
9. [Known limitations](#9-known-limitations)
10. [Edge cases and failure modes](#10-edge-cases-and-failure-modes)
11. [Implementation traps — read before editing](#11-implementation-traps--read-before-editing)

**Part III — Where next**

12. [Ranked roadmap with sizing](#12-ranked-roadmap-with-sizing)
13. [Other ways to adapt the algorithm](#13-other-ways-to-adapt-the-algorithm)
14. [Open questions for the room](#14-open-questions-for-the-room)

---

# Part I — How It Works

## 1. The problem in plain terms

Every planning day we're handed:

- a set of **orders** — jobs at customer locations, each with a required skill set, a
  time window, and a service duration;
- a set of **workers** — nurses or technicians (whichever the company does), each with
  skills and a shift;
- a set of **drivers and vehicles** — the shuttle fleet, with seating capacities.

The workers **do not drive themselves**. They are ferried between jobs by drivers. That
single fact is what makes this harder than a textbook delivery problem: we're solving two
coupled problems at once.

1. **Who does what, in what order?** — assign orders to workers and sequence them.
   This is a Vehicle Routing Problem with Time Windows (VRPTW) plus skill matching.
2. **Who drives whom, when?** — every hop a worker makes needs a driver and a seat, and
   several workers heading to the same neighbourhood at the same time should share a ride.
   This is a Dial-A-Ride Problem (DARP) — people as cargo, with ride-sharing.

Both are NP-hard. Coupled, the exact-optimal answer is unreachable for any realistic
instance size. So we don't look for the optimum — we look for a **good answer, fast, that
never crashes**.

> **The one-sentence version:** *We generate a workable plan in seconds,
> then spend a fixed time budget repeatedly tearing pieces of it apart and rebuilding them
> better, keeping what improves and occasionally accepting what doesn't so we don't get
> stuck.*

---

## 2. Why ALNS, and how ALNS works

### The idea

**Adaptive Large Neighborhood Search** is a *ruin-and-recreate* metaheuristic — meaning it
doesn't try to calculate the perfect answer, it repeatedly wrecks part of a decent answer
and rebuilds it, keeping whatever turns out better. One iteration:

```
current solution
      │
      ▼
  DESTROY  ── pick an operator, rip out ~10–30% of the assignments
      │
      ▼
  REPAIR   ── pick an operator, reinsert everything cleverly
      │
      ▼
  EVALUATE ── is the new solution better? cheaper? acceptable?
      │
      ▼
  ACCEPT / REJECT  ──► becomes the new current solution, or is discarded
      │
      ▼
  LEARN    ── reward the operator pair based on how it did
```

Repeat until the time budget expires. Keep the best solution ever seen.

*("Operator" appears twice in that diagram — the next section explains what one is.)*

### What an "operator" actually is

The word *operator* comes up constantly below, so it's worth pinning down first. It sounds
like a piece of machinery. It isn't. **An operator is just a strategy — a rule for deciding
which parts of the plan to change.** Each one is a small, self-contained function with a
name.

Picture a whiteboard with the day's plan on it: every worker has a column, and their jobs
are sticky notes stacked in the order they'll do them.

- A **destroy operator** is a rule for *which sticky notes to pull off the board.* One rule
  says "grab a handful at random." Another says "grab the notes causing the worst delays."
  A third says "grab the notes whose driver pickup went worst." Different rules, same job:
  choose what to remove.

- A **repair operator** is a rule for *where to stick them back on.* One rule says "put each
  note wherever it fits cheapest, one at a time." Another says "figure out which note has
  the fewest good options left and place that one first, before someone else takes its
  slot."

That's the whole concept. Pull some notes off, put them back somewhere better, see if the
board improved. Everything else in ALNS is bookkeeping around that loop.

**Why have more than one of each?** Because no single rule is good in every situation.
"Remove the worst-performing jobs" is smart most of the time — but it keeps grabbing the
*same* jobs, so the plan stops changing in any interesting way. "Remove random jobs" is
dumb most of the time, but it's the one that shakes the plan loose when the smart rule has
painted itself into a corner. You want both, and you don't know in advance how much of
each.

**That's what "adaptive" means.** The solver doesn't pick between them by a fixed schedule
— it keeps score. Every iteration, whichever pair of rules it used gets graded on how the
result turned out, and rules that have been earning good grades lately get chosen more
often. So a rule that works well on *today's* particular set of jobs gets used more today,
without anyone configuring that. It's less clever than it sounds — it's a weighted coin
flip whose weights drift — but it means we don't have to guess the right mix per instance.

> **Terminology bridge.** From here on: *destroy* / *remove* / *ruin* all mean pulling jobs
> out of the plan. *Repair* / *insert* / *recreate* all mean putting them back. An
> *iteration* is one full destroy-then-repair-then-evaluate cycle. The *objective* (or
> *cost*) is the single number scoring how good a plan is — **lower is better**, and it's
> the only thing the search is trying to reduce.

### The three properties that matter

**Large neighborhoods.** Classical local search nudges one thing at a time — swap two
stops, move one order. It gets trapped in local optima quickly. ALNS removes 10–30% of the
solution and rebuilds it, so a single iteration can cross a valley that a thousand small
moves couldn't.

**Adaptivity.** We don't know in advance which destroy/repair pairing works for a given
instance. So the solver keeps a score per operator and picks by weighted roulette. Operators
that recently produced new bests get picked more; ones that keep producing rejects fade.
The solver tunes *itself* per instance.

**Escape via acceptance.** A strictly-improving search stalls. Simulated Annealing accepts
worse solutions with a probability that decays over the run — exploratory early, greedy
late.

### Why it fits *us* specifically

| Requirement | Why ALNS delivers |
|---|---|
| Messy, growing constraint set | Constraints are cost terms. Adding one = adding a class, not re-deriving a model. |
| Must return *something*, always | Anytime algorithm — interrupt at any point, get the best-so-far. |
| Runtime is a business decision | The stop criterion is wall-clock. Ops decides 10s or 5min; the code is unchanged. |
| Two coupled sub-problems | Nothing needs to be linear, convex, or even continuous. Just computable. |

We use the [`alns`](https://pypi.org/project/alns/) Python library for the loop
scaffolding — acceptance, selection, statistics — and supply our own state, operators, and
objective.

**[Deep] The alternative we rejected.** Google OR-Tools CP-SAT gives proven optimality
bounds, but the pooled-shuttle coupling is awkward to express and every new constraint means
re-deriving the model. Some legacy OR-Tools plumbing survives in
[src/services/matrix.py](../src/services/matrix.py) (see `PENALTY_SEC` in
[config.py](../src/core/config.py#L45)) — worth a cleanup pass.

---

## 3. Our specific design: worker-centric state, derived driver routes

This is the most important architectural decision in the engine, and the one most worth
discussing.

### The decision

A solution — [`RoutingState`](../src/services/alns/state.py#L112) — stores **only two
things**:

```python
worker_routes: dict[int, list[int]]   # worker_id -> ordered list of order_ids
unassigned:    list[int]              # orders nobody is doing
```

That's it. **No driver assignments. No vehicle assignments. No shuttle legs.**

The entire driver-shuttle schedule is *derived* on demand by
[`derive_driver_routes()`](../src/services/alns/state.py#L226) — a deterministic pass that
reads the worker sequences and answers "given these sequences, who drives whom?"

### Why: the search space collapses

Searching over `(worker assignments × sequences × driver assignments × vehicle assignments
× shuttle timings)` is enormous. Searching over `(worker assignments × sequences)` alone is
a fraction of that. Operators get simple — they only ever move order IDs between lists —
and iterations get cheap. We measure **265–410 iterations/second** on a 20-order instance.

### How the derive pass works

For each worker sequence, walk it forward in time:

1. **Build the worker timeline** ([`_compute_visits`](../src/services/alns/state.py#L181)).
   Start at the depot at `shift_start`. For each order: travel time from the previous node
   (using the departure-hour traffic matrix) → arrival → service starts at
   `max(arrival, window_start)` → the gap is **wait** → service ends after
   `service_duration` → anything past `window_end` is **tardiness**.

2. **Emit transport events.** Every hop the worker makes (depot→first job, job→job) becomes
   a [`TransportEvent`](../src/services/alns/state.py#L52): "move worker W from node A to
   node B, available at time X, ideally arriving by time Y."

3. **Pool them** ([`_pool_events`](../src/services/alns/state.py#L310)). Two events share a
   ride if their **destinations fall in the same H3 hexagon** *and* their ideal arrival
   times fall in the same **60-minute bucket**. Implemented as a hash bucket keyed on
   `(dest_zone_h3, time_bucket)` — one linear pass, no O(n²) pairwise comparison. **This is
   the ride-sharing.** Turn `POOL_ENABLED` off and you get one trip per worker per hop.

4. **Split oversized groups** ([`_split_to_capacity`](../src/services/alns/state.py#L342)).
   If eight workers want the same hex in the same hour but the biggest van seats four, the
   group splits into two staggered legs rather than being declared impossible.

5. **Assign a driver per group** ([`_pick_driver`](../src/services/alns/state.py#L358)).
   Greedy earliest-arrival: for every driver, compute deadhead (their current position →
   pickup) plus carry (pickup → destination); take whoever arrives soonest, subject to
   *driver-can-drive-this-vehicle-type* and *vehicle-seats-everyone*.

6. **Record the delay, don't fail.** Each rider's actual arrival is compared to *their own*
   `needed_by`. Any shortfall lands in `delayed_events` for the cost function to price.

### The critical property: it never hard-fails

The derive pass **always** produces a schedule. No driver available? Every rider in that
group gets recorded as maximally delayed and `ShuttleInfeasibilityCost` fires loudly. This
matters because:

- **The search space stays connected.** There are no forbidden regions the search has to
  route around — every state is reachable and evaluable, so ALNS can pass *through* a bad
  solution on its way to a good one.
- **Infeasibility becomes a gradient, not a cliff.** "40 minutes late" scores worse than
  "5 minutes late", so the search knows which direction to move. A hard constraint gives no
  such signal — it's just `False`.

### The honest cost of this design

**The driver layer is never searched, only computed.** Given a fixed set of worker
sequences, our greedy driver assignment might be well short of the best possible one, and
ALNS has no way to find that out — it can only change the worker sequences and hope the
derive pass responds well. A full DARP formulation would search both layers jointly and
find better answers. This is the single biggest known optimality gap in the engine, and
[§12](#12-ranked-roadmap-with-sizing) sizes the fix.

---

## 4. The search loop, operator by operator

Wired in [solver.py](../src/services/alns/solver.py#L78).

> **Reading the tables below.** These are the actual rules from
> [§2](#what-an-operator-actually-is), with their real function names. We have **three
> destroy rules** (ways of choosing what to pull out of the plan) and **three repair rules**
> (ways of choosing where to put things back) — though only two repair rules are active by
> default; the third is opt-in, for the reason explained under the trade-off below. Each
> iteration picks one destroy and one repair, and the adaptive scoring decides which
> pairings get used most. Every operator's name says what it does: `worst_removal` removes
> the worst-performing orders, `greedy_insertion` inserts greedily, and so on.

### Initial solution

[`build_initial_solution`](../src/services/alns/solver.py#L69): start from empty, run
`greedy_insertion` once. Fast, mediocre, complete — exactly what a starting point should be.
Its objective becomes the baseline for the reported improvement %.

### Destroy operators — [destroy.py](../src/services/alns/operators/destroy.py)

Each removes `destroy_pct_range` (default 10–30%) of the currently-assigned orders back into
the unassigned pool.

| Operator | What it does | Why it's there |
|---|---|---|
| [`random_removal`](../src/services/alns/operators/destroy.py#L38) | Removes N orders uniformly at random | **Diversification anchor** — i.e. the one that shakes things loose. The only operator with no bias, so it's what escapes traps the guided operators built. |
| [`worst_removal`](../src/services/alns/operators/destroy.py#L51) | Removes the orders with the highest `tardiness + wait` | **Intensification** — i.e. fixing what's visibly broken. Targets the orders actively hurting the objective. |
| [`shuttle_cost_removal`](../src/services/alns/operators/destroy.py#L77) | Removes the orders whose derived shuttle leg had the worst pickup delay | **Our domain-specific one.** Directly attacks whatever `ExcessWaitCost` / `ShuttleInfeasibilityCost` flagged. Falls back to random when nothing is shuttle-expensive. |

The guided operators add microscopic random jitter (`rng.uniform(0, 1e-6)`) to their scores
so ties don't always break the same way — otherwise they'd deterministically remove the same
orders every iteration and the search would cycle.

### Repair operators — [repair.py](../src/services/alns/operators/repair.py)

Each reinserts every unassigned order. All are **hard-filtered by skill** — an order is only
offered to workers holding all its required skills.

> **First, what "cheap proxy" means in the table below.** A *proxy* is a stand-in
> measurement: something quick to compute that you use in place of the thing you actually
> care about, because measuring the real thing is too expensive. (Like using resting heart
> rate as a proxy for general health — fast, roughly right, occasionally wrong.)
>
> Here, the thing we actually care about is *"if I put this job on this worker at this
> position, how much worse does the whole plan get?"* Answering that honestly means running
> the full driver-scheduling pass: recompute the timeline, redo the ride-pooling, reassign
> drivers, re-price everything.
>
> The problem is how often we'd have to ask. A repair operator tries **every unassigned
> order × every skilled worker × every position in that worker's day** — hundreds of
> candidate placements — and it does that on every one of the ~400 iterations per second.
>
> So the *cheap proxy* cuts a corner: it looks only at the worker's own timeline (does this
> make them late? does it make them wait?) and **skips driver scheduling entirely** — it
> never checks whether a driver is actually free to get them there. Roughly 50× faster, and
> sometimes wrong. The `shuttle_aware` operator is the honest version that pays full price.
> Which is better is [measured below](#deep-the-proxy-vs-accurate-trade-off--measured-not-assumed),
> and the answer may surprise you.

| Operator | Selection rule | Cost model |
|---|---|---|
| [`greedy_insertion`](../src/services/alns/operators/repair.py#L89) | Each order (shuffled) goes to its globally cheapest (worker, position) | Cheap proxy |
| [`regret2_insertion`](../src/services/alns/operators/repair.py#L115) | Place the order with the largest gap between its best and second-best option, first | Cheap proxy |
| [`shuttle_aware_greedy_insertion`](../src/services/alns/operators/repair.py#L155) | Same shape as greedy | **True objective** — full derive per candidate |

**Why regret-2 exists.** Greedy is myopic: it happily takes an easy order's cheapest slot,
then discovers the order that *only* had one good option has lost it. Regret-2 asks "how
much will I regret *not* placing this now?" — the gap between best and second-best — and
places the highest-regret order first. Orders with exactly one feasible worker get an
artificial `+1e6` regret so they're always placed first.

### **[Deep]** The proxy-vs-accurate trade-off — measured, not assumed

The cheap proxy ([`_proxy_insertion_cost`](../src/services/alns/operators/repair.py#L32))
scores a candidate insertion using only worker-timeline terms — tardiness, excess wait, and
end-of-day time as a light travel proxy — **without** running the driver-scheduling pass.
The shuttle-aware variant trial-inserts, calls `state.objective()` (full derive), and
reverts.

Benchmarked via [`benchmark_repair_modes()`](../src/services/alns/solver.py#L182) on 20
orders / 4 workers / 3 vehicles, seed 42, 8s each:

| Mode | Best objective | Iterations/sec | Improvement over initial |
|---|---|---|---|
| `proxy` | 10,764 | 410 | +17.7% |
| `shuttle_aware` | **10,378** | 265 | **+20.7%** |

**Shuttle-aware wins by ~3.6% on objective despite ~35% fewer iterations.** Pricing real
shuttle feasibility at insertion time beats raw search throughput at this size.

The default is nonetheless `proxy`, because that gap is expected to invert as instances
grow — shuttle-aware is O(workers × positions) full derives per order, and the derive pass
itself grows with the instance. **This is a live tuning question, not a settled one, and
it's worth re-measuring at 100+ orders** ([§14](#14-open-questions-for-the-room)).
Callers choose per-run via `repair_mode` in the create-plan request.

### Acceptance, selection, stopping

| Component | Choice | Configuration |
|---|---|---|
| **Accept** | `SimulatedAnnealing` | 100.0 → 1.0, geometric step 0.9995 |
| **Select** | `SegmentedRouletteWheel` | scores `[5, 2, 1, 0.5]`, decay 0.8, segment 100 |
| **Stop** | `MaxRuntime` | 60 seconds default |

**Reading the selection scores:** an operator pair earns **5** for a new global best, **2**
for beating the current solution, **1** for being accepted anyway, **0.5** for rejection.
Weights update every 100 iterations, blending 80% history with 20% new evidence — responsive
enough to adapt, damped enough not to thrash on noise.

**Runtime as the stop criterion** is deliberate: it makes solve time a product decision, not
an engineering one, and it makes the endpoint's latency predictable regardless of instance
size (quality degrades gracefully instead).

### Live progress

For the SSE stream, all four ALNS outcome callbacks are hooked
([solver.py](../src/services/alns/solver.py#L158)): `on_best` emits immediately, the other
three emit a throttled snapshot every 50 iterations. This is why the progress bar keeps
moving during long stretches with no new best. Every callback is wrapped in a bare `except`
— **progress reporting must never break a solve**.

---

## 5. The objective function

[cost.py](../src/services/alns/cost.py). Every term is a `CostComponent` subclass; the
objective is their sum. `compute_cost` never changes when a constraint is added — you write
one class and append it to `COST_COMPONENTS`.

| Component | Measures | Default weight |
|---|---|---|
| [`TravelTimeCost`](../src/services/alns/cost.py#L32) | Total driver travel seconds across shuttle legs | raw seconds (weight 1) |
| [`FuelCost`](../src/services/alns/cost.py#L41) | `distance_km × fuel_average × price` per leg | PKR, from `FUEL_PRICES` |
| [`TardinessCost`](../src/services/alns/cost.py#L65) | Service ending after the order's window closes | 2.0 / minute |
| [`OvertimeCost`](../src/services/alns/cost.py#L81) | Worker's last service ending past `shift_end` | 3.0 / minute |
| [`SkillViolationCost`](../src/services/alns/cost.py#L105) | Worker assigned a job they aren't qualified for | 200.0 flat |
| [`UnservedOrderCost`](../src/services/alns/cost.py#L126) | Orders left in the unassigned pool | 500.0 each |
| [`ExcessWaitCost`](../src/services/alns/cost.py#L135) | Worker idle time + shuttle pickup delay beyond 15 min | 5.0 / minute |
| [`ShuttleInfeasibilityCost`](../src/services/alns/cost.py#L164) | Transport events undeliverable within 45 min | 300.0 flat |

All weights come from `state.penalties`, resolved from config and overridable per run —
**tuning is data, not code.**

### What the weight ratios actually encode

These numbers are a policy statement, and they should be reviewed by someone who knows the
business, not just the engineers:

- **Unserved (500) > infeasible shuttle (300) > skill violation (200).** Never serving a
  customer is the worst outcome. Note that skill violation being *cheapest* of the three is
  arguably wrong — sending an unqualified nurse could be a compliance issue, not a
  414-point-cheaper inconvenience. It's currently near-impossible because insertion is
  hard-filtered, so this is a safety net rather than an active trade-off — but the ordering
  is worth a deliberate decision.
- **Overtime (3/min) > tardiness (2/min).** Burning out staff costs more than a late
  arrival. Defensible, and exactly the kind of thing operators should be able to flip.
- **Excess wait (5/min) is the highest per-minute rate.** A worker standing on a kerb waiting
  for a driver is paid, idle, and unhappy. This is the term that drives good pooling.
- **`TravelTimeCost` is unweighted raw seconds** — a 1.0/second multiplier, i.e. 60/minute,
  making it *by far* the heaviest per-minute term in the objective. This is almost certainly
  unintentional and is discussed in [§9](#9-known-limitations) as a real concern.

### Free thresholds

`EXCESS_WAIT_THRESHOLD_MIN = 15` — a worker may wait 15 minutes for free; only the excess is
priced. This stops the solver contorting the plan to shave a two-minute wait.

`SHUTTLE_INFEASIBLE_AFTER_MIN = 45` — past 45 minutes of pickup delay, the flat
infeasibility penalty fires *on top of* the accumulating wait cost. Note these two terms
**both** apply to a badly-delayed pickup; that's deliberate double-pricing.

---

# Part II — Inputs, Knobs, and Where It Breaks

## 6. Inputs and how an instance is built

[`load_problem_data()`](../src/services/alns/problem_data.py#L410) turns a
`(company_id, planned_date)` pair into an immutable
[`ProblemData`](../src/services/alns/problem_data.py#L270) — loaded once, **shared read-only
across every iteration, never copied**. Only the mutable solution is copied.

### What gets loaded

| Input | Source | Filters applied |
|---|---|---|
| **Depot** | `Depot` (first by ID for the company) | Must have a location or the load fails |
| **Orders** | `Order` | `status ∈ {pending, assigned}`, `service_date == planned_date`, `location_id NOT NULL`; optionally restricted to a caller-supplied `order_ids` |
| **Workers** | `Nurse` or `Technician`, by `Company.service_type` | `operational_status == active`, `deleted_at IS NULL` |
| **Vehicles** | `Vehicle` | All for the company |
| **Drivers** | `Driver` | All for the company |

Per order we read: required skills (from the nurse *or* tech column, whichever the company
uses), time window, service duration (falling back to `DEFAULT_SERVICE_DURATION_MIN = 30`),
priority, weight, volume. **Weight and volume are loaded but currently unused** — no cost
term reads them.

### The travel-time stack

The performance-critical piece. Rather than computing travel times during the search, we
precompute a **per-hour matrix stack**: `travel_time_sec[hour][i][j]`, hours 0–23, indices
into `nodes` (depot at index 0).

Distances are traffic-independent, so the expensive routing runs **once**; each hour's matrix
is the free-flow matrix scaled by that hour's traffic multiplier
([`build_travel_stack`](../src/services/alns/problem_data.py#L379)). Hours are limited to the
span of worker shifts ([`_infer_active_hours`](../src/services/alns/problem_data.py#L589),
fallback 8–18); a departure hour outside that span snaps to the nearest built hour.

**Two providers**, behind the `TravelTimeProvider` interface:

- **[`OSMnxProvider`](../src/services/alns/problem_data.py#L174)** (production) — real road
  network. Snaps each node to the nearest graph node, runs `shortest_path` for every ordered
  pair, and **caches the GeoJSON geometry per leg** so persisted routes follow real roads on
  the map. Traffic multipliers come from `TrafficProfile` rows via zone + hour.
- **[`HaversineProvider`](../src/services/alns/problem_data.py#L126)** (synthetic/tests) —
  great-circle distance ÷ average speed. Milliseconds instead of minutes.

**Fallback policy** ([`_resolve_provider`](../src/services/alns/runner.py#L33)) — a
deliberate distinction worth defending in the meeting: if the road *graph* can't load at all
(download or Redis failure), that's **infrastructure** — we warn loudly on the stream and
degrade to Haversine so a demo survives. If an individual *location* can't be routed, that's
**bad data** — we raise `LocationUnroutable` and fail the solve visibly. Silent degradation
on bad data would let a wrong plan look like a right one.

### Cost of instance building **[Deep]**

The OSMnx path is **O(n²) shortest-path computations** for n nodes. This dominates the
wall-clock time for a real solve and is not counted in the ALNS runtime budget. 50 orders =
2,601 routed pairs. **This, not the ALNS loop, is the current scaling bottleneck.**

---

## 7. Constraints: hard, soft, and absent

Understanding which bucket a constraint is in tells you what the solver *can't* do wrong,
what it *can* do wrong for a price, and what it doesn't know about.

### Hard — structurally impossible to violate

| Constraint | Enforced by |
|---|---|
| Worker must hold all required skills | Insertion is filtered by [`_feasible_workers`](../src/services/alns/operators/repair.py#L79) |
| Driver must be eligible for the vehicle type | [`driver_can_drive`](../src/services/alns/problem_data.py#L336) filter in `_pick_driver` |
| A vehicle can't carry more than `seating_capacity` | Capacity filter in `_pick_driver` + `_split_to_capacity` |
| A worker is in one place at a time | Implicit in the sequential timeline walk |
| A driver is in one place at a time | `driver_state[id]["free_sec"]` advances after each leg |

### Soft — violable at a price

Time windows, shift ends, wait time, shuttle deliverability, order coverage, and skills (as
a redundant safety net). All are cost terms; see [§5](#5-the-objective-function).

**The design principle:** anything that could make a solution *unreachable* is soft. Only
constraints that can be enforced by *never generating* the violation are hard.

### Absent — the solver doesn't know these exist

This is the list to read out loud in the meeting.

- **Lunch breaks and mandatory rest.** No break is reserved. A worker can be scheduled
  09:00–17:00 solid. Legally and practically wrong.
- **Per-worker start/end locations.** Everyone starts at one shared depot. Real workers start
  from home, or from different depots. Also: **nobody returns to the depot** — the day ends
  wherever the last job was, and no return leg is costed.
- **Road restrictions.** One-way streets, height/width limits, closures, truck routing — all
  ignored. The network is idealized.
- **Vehicle range, refuelling, charging.** Unlimited.
- **Driver shifts and driver breaks.** Drivers are modelled as available from second zero
  (`free_sec: 0.0`) to infinity. Only *workers* have shifts.
- **Order priority.** It's loaded into `OrderInfo.priority` and **read by nothing.** A
  `critical` order is worth exactly the same 500 points as a `normal` one when unserved.
  This is a small fix with real business value.
- **Order weight/volume, and equipment.** Loaded, unused. Vehicles are transport-only.
- **Idle-worker cost.** An unused worker is free, so the solver will happily leave someone
  idle all day. Deliberate for now — but it means the plan won't naturally balance workload.
- **Continuity / customer preference.** No notion of "this patient should see the same nurse."
- **Multi-day.** Strictly single-date by construction.

---

## 8. Every tunable parameter

### Loop control — `ALNS_CONFIG` ([config.py](../src/core/config.py#L107))

Overridable per run via `config_overrides` in the create-plan request.

| Parameter | Default | Effect | Guidance |
|---|---|---|---|
| `max_runtime_sec` | 60 | Wall-clock budget | The primary quality dial. Diminishing returns — most gain is in the first third. |
| `seed` | 42 | RNG seed | **Fixed for reproducibility.** Same inputs + same seed = same plan. Vary it to sample the solution space. |
| `sa_start_temp` | 100.0 | Initial acceptance appetite | Should be scaled to typical objective magnitude — see [§9](#9-known-limitations). |
| `sa_end_temp` | 1.0 | Final appetite (≈ greedy) | Rarely touched. |
| `sa_step` | 0.9995 | Geometric cooling rate | **Must be matched to iteration count.** At 0.9995, temp reaches 1.0 in ~9,200 iterations. |
| `destroy_pct_range` | `[0.1, 0.3]` | Fraction of orders removed per iteration | Higher = bigger jumps, slower iterations. Standard ALNS territory. |
| `progress_emit_every` | 50 | SSE throttle | Cosmetic. |

**[Deep] The cooling-rate coupling is the subtle one.** `sa_step` is per *iteration*, but the
stop criterion is *time*. At 400 it/s and 60s you get ~24,000 iterations — the temperature
bottoms out around iteration 9,200 and the last 60% of the run is effectively a greedy hill
climb. On a slower instance at 50 it/s and 60s, you get 3,000 iterations and the search never
finishes cooling — it stays exploratory the whole time and never converges. **Neither is a
tuned schedule.** See [§12](#12-ranked-roadmap-with-sizing), item 4.

### Objective weights — `ALNS_PENALTIES` ([config.py](../src/core/config.py#L69))

`tardiness_per_min` 2.0 · `overtime_per_min` 3.0 · `skill_violation` 200.0 ·
`unserved_order` 500.0 · `excess_wait_per_min` 5.0 · `shuttle_infeasible` 300.0

Overridable per run. **These are the business-policy dial** — see
[§5](#5-the-objective-function) for what the ratios encode. A
[`cost_profile`](../src/db/models/cost_profile.py) model exists to hold these per company,
but is not yet wired to the API or UI.

### Thresholds

`EXCESS_WAIT_THRESHOLD_MIN` 15 · `SHUTTLE_INFEASIBLE_AFTER_MIN` 45 ·
`DEFAULT_SERVICE_DURATION_MIN` 30

### Ride-pooling

| Parameter | Default | Effect |
|---|---|---|
| `POOL_ENABLED` | `True` | Master switch. Off ⇒ one shuttle trip per worker per hop. |
| `POOL_WINDOW_MIN` | 60 | Riders whose ideal arrivals fall in the same bucket can share. Wider = more sharing, more waiting. |
| `POOL_H3_RESOLUTION` | 8 | H3 cell size defining "same area". Res-8 ≈ 460 m. Coarser = more sharing, longer detours. |

**`POOL_WINDOW_MIN` and `POOL_H3_RESOLUTION` are the two highest-leverage untuned knobs in
the system** — they directly set the fleet-efficiency vs. worker-wait trade-off, and neither
has been swept.

**[Deep] The bucketing is fixed-boundary, not sliding.** With a 60-minute window, riders at
10:59 and 11:01 land in different buckets and won't pool, while 10:01 and 10:59 will. That's
the price of the O(n) hash-bucket approach over O(n²) pairwise clustering — and it's a real
missed-pooling source at bucket edges.

### Economics

`FUEL_PRICES` (PKR/litre): petrol 280 · diesel 290 · CNG 190 · electric 60 (per kWh).
Per-vehicle `fuel_average` and `avg_speed_kmh` come from the `Vehicle` row.

### Per-run switches

`repair_mode` — `"proxy"` (default) or `"shuttle_aware"`. `force_haversine` — skip OSMnx
entirely (dev/testing).

---

## 9. Known limitations

Ordered by how much they'd worry me. The first three are things I'd want fixed before
anyone treats an objective number as meaningful.

### 9.1 The travel-time term is unweighted raw seconds

`TravelTimeCost` returns a bare sum of seconds — implicitly weight 1.0 **per second**, i.e.
**60 per minute**, against tardiness at 2/minute and excess wait at 5/minute. Travel time is
therefore ~12–30× heavier per minute than any human-impact term, and one hour of shuttle
driving (3,600) outweighs seven unserved orders (3,500).

I don't believe that's the intended policy, and it means **the objective is currently
dominated by driver travel time.** This is the single highest-value thing to fix: it needs a
`travel_time_per_min` weight in `ALNS_PENALTIES` and then a re-tune of everything else
against it. Every other weight in the table was chosen against a scale this term silently
overwhelms.

### 9.2 The driver layer is derived, never searched

Covered in [§3](#3-our-specific-design-worker-centric-state-derived-driver-routes). Greedy
earliest-arrival driver assignment with no lookahead: a driver taken now for a marginal gain
may be the only one who could have served a critical pickup twenty minutes later. We have no
measurement of how large this gap is — **quantifying it against a reference DARP solver on a
small instance would be genuinely informative** and is cheap to do.

### 9.3 Absolute objective values are meaningless across instances

The objective mixes seconds, PKR, and arbitrary penalty points into one unitless scalar.
It's a valid *search* signal but not a valid *business* metric. Comparing plan A's 10,378 to
plan B's 12,000 across different days or companies tells you nothing. Only the per-component
breakdown and the improvement % are interpretable — and the dashboard should say so.

### 9.4 SA temperature is not scaled to the objective

Start temp 100 against objectives in the 10,000+ range means `exp(-Δ/T)` rejects almost any
meaningful worsening from iteration one. **The search may be behaving closer to a hill
climber than to annealing.** The standard fix is to set the start temperature from the
initial solution's objective (e.g. accept a 5% worsening with 50% probability at the start)
rather than from a fixed constant. Worth verifying empirically before assuming it's broken —
but the acceptance-rate trace in the diagnostics would show this immediately.

### 9.5 O(n²) matrix construction dominates real solve time

See [§6](#6-inputs-and-how-an-instance-is-built). Also: the per-hour stack is
`hours × n × n` floats held in memory. 200 orders × 11 hours ≈ 440k floats — fine, but
it grows quadratically.

### 9.6 Single-threaded

One solve uses one core. Multiple concurrent solves are FastAPI `BackgroundTasks` in-process,
so they contend for the GIL. Celery is already flagged in
[Future Improvements](Future%20Improvements%20&%20Concerns.md).

### 9.7 The pooling model is not true DARP

Real DARP has explicit pickup-delivery pairing with precedence constraints, maximum ride
times per passenger, and joint routing. We have zone-and-time bucketing with a greedy
assignment. It produces sensible ride-sharing and is far simpler — but a worker's total time
in a vehicle is never bounded, so a pooled rider could in principle take a long detour with
no penalty beyond the arrival delay.

### 9.8 No test coverage

[tests/](../tests/) contains only `__init__.py`. For a stochastic optimizer this is a real
risk — see [§12](#12-ranked-roadmap-with-sizing), item 1.

---

## 10. Edge cases and failure modes

### Handled, with the intended behaviour

| Situation | What happens |
|---|---|
| No worker has an order's skills | Order stays unassigned, `UnservedOrderCost` fires, reason recorded in diagnostics |
| No driver at all, or none with capacity | Group marked maximally delayed, `ShuttleInfeasibilityCost` fires per rider |
| Pooled group exceeds every vehicle | Split into capacity-sized staggered legs |
| Order has no time window | `service_start = arrival`, tardiness = 0. Effectively unconstrained. |
| Worker has no `shift_end` | Overtime not computed for them — **they can be scheduled indefinitely** |
| Driver has no `vehicle_id` | Skipped entirely in `_pick_driver` |
| Driver has empty `skills` | Treated as **unrestricted** — can drive anything |
| Order has no `required_skills` | Any worker can serve it |
| Order has no `service_duration_min` | Falls back to 30 minutes |
| Departure hour outside the built stack | Snapped to nearest active hour |
| Road graph won't load | Warn on stream, degrade to Haversine, continue |
| A location can't be routed | `LocationUnroutable` → plan marked `failed`, `error_code: location_unroutable` |
| Any unexpected exception | Caught in `run_solve`, plan → `failed`, error streamed. **The background task never crashes silently.** |
| `POOL_ENABLED = False` | Every event is its own singleton group |

Note the pattern in rows 6, 7, and 8: **missing data is interpreted permissively.** A driver
with no listed skills can drive anything; a worker with no shift end never works overtime.
That's the right default for a demo with incomplete seed data and the wrong default for
production, where missing data more likely means "not yet configured" than "unrestricted."

### Genuinely unhandled

| Situation | Consequence |
|---|---|
| **Zero orders** | Empty `nodes` beyond the depot; likely degenerate or an exception. Untested. |
| **Zero workers** | Everything unassigned. Objective = `n × 500`. Technically correct, operationally useless. |
| **Time window crossing midnight** | Everything is seconds-since-midnight on one date. A 22:00–02:00 window will compute nonsense. |
| **Overnight shift** | Same. `shift_end < shift_start` breaks the arithmetic. |
| **Timezone / DST** | Times are naive wall-clock. `_sec_to_dt` stamps UTC on persist. A DST transition on the planned date shifts everything by an hour. |
| **Duplicate locations** | Two orders at identical coordinates snap to the same graph node; travel time 0. Probably fine, never verified. |
| **`initial_objective == 0`** | `improvement_pct` guards division but silently reports 0.0%. |
| **Worker with a shift but no reachable orders** | Idle, costs nothing, no diagnostic explains why. |

---

## 11. Implementation traps — read before editing

Concrete mistakes that are easy to make in this codebase. Worth walking through with anyone
new to the solver.

### 11.1 Destroy operators MUST copy first

The `alns` library **does not defensively copy**. On entry, `current`, `best`, and `initial`
may all be *the same object*. A destroy operator that mutates its argument corrupts the
incumbent and the best-known solution simultaneously — and the symptom is a mysteriously
degrading best objective, not a crash.

```python
def my_removal(state, rng):
    state = state.copy()   # ← non-negotiable, FIRST LINE
    ...
```

Repair operators receive the already-copied destroyed state and may mutate freely. This
asymmetry is documented at the top of
[destroy.py](../src/services/alns/operators/destroy.py#L10) — please keep it there.

### 11.2 Mutating `worker_routes` without invalidating the cache

`derive_driver_routes()` caches into `_derived`. Any mutation must call `invalidate()`.
`assign()` and `unassign()` do this for you — **so always go through them.** Touching
`state.worker_routes[w].append(oid)` directly leaves a stale schedule that silently
misprices every subsequent evaluation.

Note `copy()` deliberately does **not** copy `_derived` — the clone is about to be mutated,
so recomputing lazily is cheaper than copying a schedule that's about to be wrong.

### 11.3 Don't copy `ProblemData`

It's shared read-only by design, including the per-hour matrix stack. Copying it per
iteration would destroy performance. If you find yourself wanting to mutate it, you want a
different design.

### 11.4 The proxy cost must stay cheap

`_proxy_insertion_cost` currently rebuilds the *entire* worker timeline twice (with and
without the candidate) for every candidate position — O(seq²) per order per worker. It's
called from the innermost loop of every repair. Adding "just one more term" here that touches
the derive pass silently converts the proxy into the shuttle-aware operator, at which point
you have two of the same thing and no fast option. **If you need shuttle awareness, use the
existing operator.**

### 11.5 `shuttle_cost_removal` maps legs back to orders by `to_node`

It builds `node_to_order` from `to_node`. Since a pooled leg's `to_node` is only the
*representative* destination, the per-rider `rider_to_nodes` mapping is what's actually
accurate. **Riders whose own destination differs from the representative are currently not
attributed their share of a bad leg** — a small correctness gap in the operator's targeting,
not in the cost function.

### 11.6 Progress callbacks must never raise

Everything inside `_emit` is wrapped. A callback exception would abort a 60-second solve to
fail at drawing a progress bar. If you extend it, keep the guard.

### 11.7 Seconds-since-midnight is the universal unit

Every time inside the solver is a float of seconds from midnight on the planned date.
`datetime` conversion happens **only** at the persistence boundary
([`_sec_to_dt`](../src/services/alns/persistence.py#L123)). Introducing a `datetime` inside a
cost component or operator will produce type errors at best and wrong arithmetic at worst.

### 11.8 Adding a cost component: two things, not one

Write the subclass **and** append it to `COST_COMPONENTS`. A component that isn't in the list
is silently ignored — no error, just a constraint that quietly doesn't exist. Also give it a
default weight in `ALNS_PENALTIES` and have it early-return `0.0` when its rate is zero
(every existing component does this, and it keeps the objective cheap when a term is
disabled).

### 11.9 Determinism is a feature — don't break it

The seed is fixed at 42 so the same inputs produce the same plan. Introducing an unseeded
`random` call, or iterating a set where order matters, breaks reproducibility and makes
regressions impossible to bisect. Note the operators use `rng.uniform(0, 1e-6)` jitter drawn
from the *seeded* generator precisely to get tie-breaking without sacrificing determinism.

### 11.10 `regret2_insertion` recomputes the best position

After finding the best worker via `per_worker`, it calls `_best_position_proxy` again for
that worker. It's correct, and a redundant computation in the hot loop.

---

# Part III — Where Next

## 12. Ranked roadmap with sizing

Sizing is engineering effort: **S** ≈ days, **M** ≈ 1–2 weeks, **L** ≈ 3+ weeks.
Ranked by impact-per-effort, not by ambition.

---

### 1. Test suite for the solver — **S** · unlocks everything below

[tests/](../tests/) is empty. For a stochastic optimizer that's the load-bearing gap: we
cannot currently tell an improvement from a regression, which makes every item below riskier
and slower than it needs to be.

What's needed: `HaversineProvider` fixtures (fast, no OSMnx), per-component cost assertions
via `cost_breakdown()`, invariant checks (no order lost or duplicated across destroy+repair
— an easy property test), the copy-semantics contract from [§11.1](#111-destroy-operators-must-copy-first),
seeded end-to-end determinism, and the edge cases in [§10](#10-edge-cases-and-failure-modes).

**Do this first.** It's the cheapest item and every other item is safer after it.

---

### 2. Fix and re-tune the objective weights — **S** · high impact

Add `travel_time_per_min` to `ALNS_PENALTIES` and re-tune every weight against it
([§9.1](#91-the-travel-time-term-is-unweighted-raw-seconds)). Right now travel time silently
dominates the objective, which means **every plan we've generated has been optimizing for
something other than what the weight table says.**

While in there: make `priority` actually do something (scale `unserved_order` and
`tardiness_per_min` by order priority — a handful of lines for real business value), and
revisit whether `skill_violation` at 200 should really be the cheapest of the three flat
penalties.

**This is arguably a bug fix, not an improvement.**

---

### 3. Per-worker start locations (MDVRP) — **M** · high business value

Every worker currently starts at one shared depot. Real workers start from home. This
inflates every first leg and produces plans that don't match reality — which undermines
trust in the output more than any optimality gap.

Mechanically it's contained: `WorkerInfo` gains a `start_node_index`; `_compute_visits` and
the transport-event loop use it instead of `pd.depot_node_index`; `nodes` grows by the number
of distinct start locations (which grows the O(n²) matrix — see item 6). Should include the
question of whether the day **ends** anywhere — currently there's no return leg at all.

---

### 4. Adaptive SA schedule and a parameter sweep — **S–M** · high impact, low risk

Two coupled problems from [§8](#8-every-tunable-parameter) and
[§9.4](#94-sa-temperature-is-not-scaled-to-the-objective): the start temperature isn't scaled
to the objective, and the cooling rate is per-iteration while the stop criterion is per-time,
so the actual annealing schedule depends on how fast the instance happens to run.

Fix: set `sa_start_temp` from the initial objective (accept a ~5% worsening with 50%
probability at the start), and derive `sa_step` from an estimated iteration count after a
short calibration burst.

Then sweep, on a fixed instance set: `POOL_WINDOW_MIN`, `POOL_H3_RESOLUTION`,
`destroy_pct_range`, and `max_runtime_sec`. These are the highest-leverage untuned knobs we
have, and none has been measured. **Cheap, purely empirical, and it needs item 1 first.**

---

### 5. Lunch breaks and mandatory rest — **S–M** · compliance-relevant

Currently a worker can be scheduled 09:00–17:00 with no break. Simplest version: reserve a
fixed break window per worker in `_compute_visits`. Better: a flexible break that must fall
within a window, which turns each worker's timeline into a small scheduling sub-problem. Not
algorithmically deep, but it touches the timeline walk that everything else reads.

---

### 6. Matrix build performance — **M** · the real scaling ceiling

O(n²) OSMnx shortest paths dominates wall-clock for real solves
([§9.5](#95-on²-matrix-construction-dominates-real-solve-time)) and is the actual barrier to
larger instances — not the ALNS loop. Options, roughly in order of payoff:

- Persistent cross-solve caching keyed on node pairs (locations are highly repeated day to
  day — likely the biggest single win for the least work)
- Batched one-to-many shortest paths instead of pair-by-pair
- Parallel matrix construction (it's embarrassingly parallel and releases the GIL in the
  OSMnx/numpy layers)
- Self-hosted OSRM/Valhalla — already flagged as a *maybe* in
  [Future Improvements](Future%20Improvements%20&%20Concerns.md); a real operational
  commitment, but it turns a matrix build from minutes into milliseconds

---

### 7. Expose cost profiles through API and UI — **S** backend / **M** with UI

[`cost_profile.py`](../src/db/models/cost_profile.py) already exists and isn't wired up.
Letting an operator say "prioritize punctuality this week" without a deploy is a visible,
demo-able capability, and it converts our weight guesses into their business decision.

Pairs naturally with item 2 — no point exposing weights we know are miscalibrated.

---

### 8. Local-search polish on the best solution — **S–M** · cheap quality gain

ALNS is good at large moves and comparatively wasteful at fine-grained ones. Running a
classical 2-opt / Or-opt pass over each worker's sequence when a new best is found is
standard practice in ALNS implementations and typically buys a few percent for very little
code. Fits neatly in the existing `on_best` hook.

---

### 9. Search the driver layer — **L** · biggest optimality gap, most risk

The structural limitation from [§9.2](#92-the-driver-layer-is-derived-never-searched). Two
routes:

- **Incremental:** add driver-layer destroy/repair operators — reassign a driver's legs,
  swap drivers between pooled groups — while keeping worker-centric state as primary. Lower
  risk, partial payoff.
- **Full:** promote driver assignments into the searched state. Much larger search space,
  slower iterations, better ceiling. This is the "proper DARP" item from
  [Future Improvements](Future%20Improvements%20&%20Concerns.md).

**Before committing to either, measure the gap** — compare our derive pass against an exact
or reference DARP solver on a deliberately small instance. If greedy is within 3%, this drops
below items 5–8. If it's 20%, it jumps to the top. That measurement is an **S** and it should
happen before the **L**.

---

### 10. ML clustering of order nodes — **L** · speculative

Flagged in [Future Improvements](Future%20Improvements%20&%20Concerns.md). Cluster
geographically coherent orders to shrink the search space.

My honest read: this is the lowest-confidence item on the list. We already have geographic
structure via H3 zones, and ALNS's whole strength is that it doesn't need a good
decomposition. Classical clustering (k-means on coordinates, capacity-constrained) would
capture most of the benefit for a fraction of the effort, and a cluster-based destroy
operator — "remove all orders in one H3 zone" — is an **S** that tests the hypothesis before
we invest in the **L**. I'd do that first.

---

### Suggested sequencing

| Phase | Items | Rationale |
|---|---|---|
| **Now** | 1, 2 | Tests, then fix the objective. Nothing else is trustworthy until both are done. |
| **Next** | 4, 3 | Tune what we have, then the highest-value modeling gap. |
| **Then** | 5, 7, 8 | Compliance, operator control, cheap quality. |
| **Ongoing** | 6 | Performance work as instance sizes grow. |
| **Investigate first** | 9 (measure), 10 (zone-destroy operator) | Buy information before buying the large item. |

---

## 13. Other ways to adapt the algorithm

Beyond incremental improvement — directions that change what the engine *is*. Discussion
material rather than roadmap.

### 13.1 Real-time re-optimization

Today the solver is batch: plan the day, execute the day. But we already have live position
events ([`vehicle_position_event`](../src/db/models/vehicle_position_event.py),
[`worker_position_event`](../src/db/models/worker_position_event.py)) and a mobile app
reporting job status. The pieces for **dynamic re-optimization** exist.

The shape: when something disrupts the plan (an order cancels, a worker calls in sick, a job
overruns, traffic collapses), re-solve **the remainder of the day** with completed stops
frozen and the current positions as the new starting points.

ALNS is unusually well-suited: freezing completed work is just "don't let operators touch
these", and warm-starting from the existing plan instead of from greedy means a 5-second
re-solve is genuinely useful. **The main new problem is *stability*** — a re-plan that
reshuffles everyone's afternoon is operationally worse than a slightly suboptimal one that
changes two stops. That means a new cost component penalizing deviation from the committed
plan, which is exactly the kind of thing our modular objective makes easy.

I'd call this the most interesting direction available to us, and closer to reachable than it
sounds.

### 13.2 Multi-day / rolling-horizon planning

Currently strictly single-date. Real operations have orders spanning date ranges ("this week"),
recurring visits ("every Tuesday"), and the option to defer a job by a day to make the whole
week better. This is a genuinely different problem — the Periodic VRP — and would need a
day-assignment layer above the current solver. It also directly addresses the multi-date
order rejection noted in [Future Improvements](Future%20Improvements%20&%20Concerns.md).

### 13.3 Multi-objective / Pareto planning

Instead of collapsing everything into one scalar, produce a **set** of non-dominated plans
and let the operator choose: "here's the cheapest, here's the most punctual, here's the most
balanced." ALNS extends to this reasonably well. It reframes the product from "the algorithm
decided" to "here are your options" — which also sidesteps the explainability problem, and
connects to the two-sided plan-rating idea already in
[Future Improvements](Future%20Improvements%20&%20Concerns.md).

### 13.4 Learning from accepted and rejected plans

Every plan an operator approves or rejects is a labelled data point about what they actually
want, which is not necessarily what our weight table says. Two levels:

- **Weight learning** — infer the cost weights implied by their choices (inverse
  optimization). Modest, tractable, and directly useful.
- **Operator selection learning** — replace the roulette wheel with a bandit or RL policy
  conditioned on instance features. Academically interesting, and honestly a small gain over
  the adaptive weights we already have.

The first is worth doing. The second I'd treat as a research curiosity.

### 13.5 Explainability

A rejected plan is currently a black box, which is a trust problem more than a technical one.
We already persist a rich diagnostics blob — cost breakdown, per-iteration trace, operator
statistics, unserved reasons. Turning that into plain language — *"Order #412 is unserved
because no active nurse holds the required skill"*, *"Worker 7 finishes 40 minutes late
because the 14:00 pickup had no driver free"* — is mostly presentation work over data we
already have. Low effort, disproportionate impact on whether operators trust the output.

### 13.6 Robust / stochastic planning

Travel times and service durations are treated as deterministic. They aren't. A plan that's
optimal under average conditions can be fragile under realistic variance. Options run from
cheap (build in time buffers proportional to leg uncertainty) to expensive (evaluate each
candidate over sampled scenarios, optimizing expected cost or a risk quantile — which
multiplies evaluation cost by the sample count). The cheap version is worth considering
early; the expensive version needs item 6 solved first.

### 13.7 Hybrid with exact methods

**First, what "exact method" means.** Everything ALNS does is *searching* — trying things,
keeping what's better. It produces good answers but can never tell you how good: there's no
way to know whether a 5% better plan was sitting just out of reach.

An **exact method** is the opposite. It doesn't wander — it *proves*. It returns the
genuinely optimal answer along with a guarantee that nothing better exists. That guarantee
is what you're buying, and it's also why these methods get slow: proving a negative
("nothing better exists") is much harder than finding something good.

The two mainstream families:

- **MIP — Mixed Integer Programming.** You express the problem as arithmetic: numeric
  variables, one formula to minimize, and a list of inequalities that must hold. *"Mixed
  integer"* means some variables are forced to be whole numbers — which matters here,
  because a variable meaning *"worker 3 rides to job 7"* has to be 0 or 1; there is no 0.4
  of a trip. The solver then works from both directions: finding progressively better
  answers, while separately proving no answer below some threshold can exist. When those two
  meet, it's finished — and it knows it's finished.

- **CP — Constraint Programming.** Same goal, very different style. Instead of arithmetic
  you state rules directly: *"these two jobs can't overlap," "this worker needs this skill,"
  "this van seats four."* The solver picks a value for something, then works out what that
  makes impossible elsewhere, which narrows the remaining options, which narrows more. Hit a
  contradiction, back up and try differently. It's much closer to how a person solves Sudoku
  than to algebra. CP tends to win on scheduling and rostering, where the rules are naturally
  logical rather than numeric. Google OR-Tools' **CP-SAT** is the well-known implementation —
  the one referenced in [§2](#2-why-alns-and-how-alns-works) as the alternative we passed on.

**Why we didn't use either for the whole problem:** they don't scale here. The coupled
worker-plus-shuttle problem is NP-hard, so the proving effort explodes as orders grow — and
every new business rule means re-deriving the model rather than adding one cost class.

**But we don't have to use them for the whole problem.** That's the actual idea here: let
ALNS handle the big messy search, then hand a small, clean *sub-problem* to an exact solver.
Two candidates:

- Optimally re-sequencing a single worker's day (small — one worker, a handful of stops).
- **Optimally assigning drivers, holding the worker sequences fixed.** This one is
  genuinely interesting: it would directly close the
  [§9.2](#92-the-driver-layer-is-derived-never-searched) gap — our greedy earliest-arrival
  driver pick — *without* redesigning the state or the operators. The expensive part of the
  problem stays with ALNS; only the tractable part goes to the exact solver.

This is a well-trodden pattern in the literature (large neighborhood search with exact
repair), not an experimental one.

---

## 14. Open questions for the room

Things I'd genuinely like decided or debated, rather than presented.

1. **Are the objective weights the business's weights?** [§5](#5-the-objective-function) is
   currently an engineer's guess at policy. Given [§9.1](#91-the-travel-time-term-is-unweighted-raw-seconds),
   the effective policy isn't even the stated one. Who owns these numbers?

2. **What's the real target instance size?** 20 orders and 200 orders imply different
   priorities — at 20, item 9 (driver search) matters most; at 200, item 6 (matrix
   performance) is the only thing that matters. This single answer reorders the roadmap.

3. **Is `proxy` still the right default?** [§4](#4-the-search-loop-operator-by-operator)
   shows shuttle-aware winning at 20 orders. The default is set for a scaling behaviour we
   haven't measured. Should we flip it until we have evidence?

4. **How much runtime is acceptable?** 60s is a guess. If ops would accept 5 minutes for a
   noticeably better plan, that's the cheapest quality improvement available and it's a
   config change.

5. **Batch or real-time?** [§13.1](#131-real-time-re-optimization) is a significant strategic
   fork and it shapes several of the roadmap items. Worth deciding direction before building
   further batch-only depth.

6. **What does "the plan was bad" mean?** We have no way to measure plan quality against
   reality — no comparison of planned versus actual times, no feedback loop. Without it we're
   optimizing a model, not the operation, and we can't tell whether any of the improvements
   above actually helped.

---

*Prepared for the ALNS review meeting, 2026-08-24. Companion to
[Future Improvements & Concerns.md](Future%20Improvements%20&%20Concerns.md) — items resolved
here should be moved out of that document rather than duplicated.*
