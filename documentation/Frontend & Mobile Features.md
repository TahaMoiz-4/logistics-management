# Nightingale — Frontend & Mobile Features

> **What this doc is:** a plain-language walkthrough of everything a person can actually
> do in Nightingale's two apps — the **web console** (used by dispatchers/admins in the
> office) and the **mobile app** (used by nurses, technicians, and drivers out in the
> field). No code, no jargon — just what each screen shows and what you can click.

---

## Web Console (Frontend)

The web console is what a dispatcher or admin uses at a desk to manage the day: see what's
going on, add new orders, build routes, and keep an eye on staff in the field.

### Login

The entry point to the console. A dispatcher/admin signs in with a username and password to
get into the system.

### Dashboard

The "home page" — a snapshot of how today is going, at a glance. It shows:

- **Delivered orders** — how many of today's orders are already done.
- **Today's schedule** — how many orders are on the books for today.
- **Available nurses** — how many field workers are currently available to be given work.
- **Order statuses** — a breakdown of where all of today's orders stand (pending, assigned,
  in transit, delivered, failed).
- **Today's route plans** — how many route plans exist for today and what state they're in
  (draft, optimizing, ready, dispatched, completed).
- **Create a new route** — a shortcut button that jumps straight into building a new route
  plan, so a dispatcher doesn't have to go hunting for it.

Think of the Dashboard as the "is everything on track?" screen — it doesn't let you edit
anything, it just tells you the state of the day.

### Orders

This is the **only page where new records are actually typed in by hand**. Every other page
in the console (Fleet, Workers, etc.) just shows lists of things that were already set up —
Orders is where a dispatcher creates new work for the system to handle.

- View every order, with filters by status (pending, assigned, in transit, delivered, failed).
- Add a brand-new order: who it's for, where it needs to happen, what skills it needs, what
  time window it should happen in, and so on.

Once orders exist here, they become available to be picked up by a route plan.

### Route Plans

This is where the "magic" of the system happens — turning a pile of orders into an actual
plan of who goes where, in what order, and who drives them there. It's not a single page so
much as a small area with a few connected screens:

- **Plans list** — every route plan that's ever been created, with its date, status, and
  a quick summary (how many orders, how many routes, how many couldn't be scheduled).
- **Create a new plan** — a dispatcher picks which orders to schedule (all from the same
  day) and hits go. This is what the Dashboard's "create a new route" shortcut also leads to.
- **Live solving view** — once a plan is kicked off, the optimizing engine (ALNS) runs and
  this screen shows it working in real time: a live-updating chart of the solution getting
  better, plus a simple progress tracker ("loading data → optimizing → saving → done").
  Think of it like a progress bar that also shows its work.
  - *Note: ALNS is the name of the optimization engine — the "planning brain" that decides
    which worker goes to which job and which driver shuttles them there, trying to find the
    most efficient combination possible.*
- **Plan detail (the finished result)** — once solving is done, this shows the actual plan
  on a map: each driver's route, which worker is doing which job, and any orders that
  couldn't be fit in (with a heads-up so the dispatcher knows). From here, a dispatcher can
  hit **Approve**, which locks the plan in and sends the jobs out to the relevant workers'
  phones.
- **Diagnostics ("solver internals")** — a behind-the-scenes report card on how well the
  optimizer did: how long it took, how much it improved the plan, a cost breakdown (travel,
  fuel, lateness, etc.), and which of its strategies worked best. This is more of a "trust
  but verify" screen for someone curious about *why* the plan looks the way it does — not
  something a dispatcher needs to check every day.

### Live Tracking

A live map showing where every field worker and vehicle currently is, based on GPS pings
sent from the mobile app. Dispatchers use this to see, in real time, who's out on the road
and whether anyone's location data has gone stale (hasn't updated recently). It also shows
a roster of who's marked themselves available vs. unavailable, and why.

### Fleet

A set of read-only lists covering everything the company owns or contracts for transport:

- **Vehicles** — the cars/vans/bikes/trucks in the fleet.
- **Drivers** — the people who drive them.
- **Depots** — the home bases vehicles and routes start/end from.

This page is for reference/lookup only — nothing here is created or edited from the console
today.

### Workers

A read-only list of field staff (nurses or technicians, depending on the company), showing
their skills, current status (active/unavailable), shift hours, and contact info. Like
Fleet, this is a viewing page — workers are added to the system elsewhere (seeded data for
now).

---

## Mobile App

The mobile app is what nurses, technicians, and drivers use out in the field on their phones.
It's a much smaller, focused experience — see your jobs, do your jobs, and let the office
know where you are.

### Login

A field worker signs in with their own username and password — separate from the web
console's login, since it's a different type of account (field staff vs. office staff).

### Home (Orders List)

The main screen after logging in — a list of the jobs assigned to that worker for the day.
From here they can:

- Tap any order to open its **details**.
- Tap **Start Shift** to begin sending their live location to the server — this is exactly
  what powers the dot that shows up for them on the web console's Live Tracking map. Until
  a worker starts their shift, the office can't see where they are.
- Tap **End Shift** to stop sending their location.
- Tap the **exit/logout icon** to sign out of the app.

### Order Details

Opened by tapping an order from the Home list. Shows the specifics of that job. From here, a
worker can:

- Tap **View Route** to see, on a map, the route from the depot to that order's location —
  so they know how they're getting there and where it is.
- Mark the order as **Complete** once the job is done.

### Availability Toggle

Reached by tapping the **person icon**. This lets a worker mark themselves as **available**
or **unavailable** for new work. If they mark themselves unavailable, they're asked for a
short reason before confirming — though in the current demo-ready version, that reason can
be left blank if the worker doesn't want to type one. This is the same status a dispatcher
sees on the web console's Live Tracking roster.

---