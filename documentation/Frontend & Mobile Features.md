# Nightingale — Frontend & Mobile App Features

> A feature reference for the two user-facing surfaces of Nightingale: the **web admin
> console** (dispatchers / operators / admins) and the **mobile app** (field workers and
> drivers). This document describes *what each surface does* from a user's perspective —
> the screens, the actions available on them, and how they fit together.
>
> **Template note:** This is a scaffold. Fill in the bullet points under each screen/section
> below. Keep entries short and user-facing ("what can someone do here / what does it show").
> Delete this note and any `_TODO_` / `_(fill in)_` placeholders once populated.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Frontend — Web Admin Console](#2-frontend--web-admin-console)
   - 2.1 [Authentication & Login](#21-authentication--login)
   - 2.2 [Dashboard](#22-dashboard)
   - 2.3 [Orders](#23-orders)
   - 2.4 [Route Plans](#24-route-plans)
   - 2.5 [Live Tracking](#25-live-tracking)
   - 2.6 [Workers](#26-workers)
   - 2.7 [Fleet](#27-fleet)
   - 2.8 [Cross-Cutting UI](#28-cross-cutting-ui)
3. [Mobile App — Field Worker Companion](#3-mobile-app--field-worker-companion)
   - 3.1 [Authentication & Session](#31-authentication--session)
   - 3.2 [Home / Today's Work](#32-home--todays-work)
   - 3.3 [Job / Order Details](#33-job--order-details)
   - 3.4 [Navigation & Live Location](#34-navigation--live-location)
   - 3.5 [Order History](#35-order-history)
   - 3.6 [Profile & Ratings](#36-profile--ratings)
   - 3.7 [Notifications](#37-notifications)
4. [Shared Concepts](#4-shared-concepts)
5. [Legend](#5-legend)

---

## 1. Overview

_(Fill in: a short paragraph on what the two surfaces are for and who uses each.)_

| Surface       | Primary users                     | Purpose                          |
|---------------|-----------------------------------|----------------------------------|
| Web console   | _Dispatchers / System Admins_    | _(fill in)_                      |
| Mobile app    | _Field workers: NUrses, Technicians, Drivers_  | _(fill in)_                      |

---

## 2. Frontend — Web Admin Console

The web console source lives under [frontend/src/](../frontend/src/); each screen below maps
to a page under [frontend/src/pages/](../frontend/src/pages/).

### 2.1 Authentication & Login

_Source: [frontend/src/pages/LoginPage.tsx](../frontend/src/pages/LoginPage.tsx)_

- _(fill in)_

### 2.2 Dashboard

_Source: [frontend/src/pages/dashboard/](../frontend/src/pages/dashboard/)_

**Overview**

- _(fill in — what the dashboard is for)_

**Widgets & metrics**

- _(fill in)_

### 2.3 Orders

_Source: [frontend/src/pages/orders/](../frontend/src/pages/orders/)_

**Orders list**

- _(fill in)_

**Create a new order**

- _(fill in)_

### 2.4 Route Plans

_Source: [frontend/src/pages/plans/](../frontend/src/pages/plans/)_

**Plans list**

- _(fill in)_

**Create a new plan**

- _(fill in)_

**Plan detail**

- _(fill in)_

**Live plan view**

- _(fill in)_

**Diagnostics**

- _(fill in)_

### 2.5 Live Tracking

_Source: [frontend/src/pages/tracking/](../frontend/src/pages/tracking/)_

- _(fill in)_

### 2.6 Workers

_Source: [frontend/src/pages/workers/](../frontend/src/pages/workers/)_

- _(fill in)_

### 2.7 Fleet

_Source: [frontend/src/pages/fleet/](../frontend/src/pages/fleet/)_

- _(fill in)_

### 2.8 Cross-Cutting UI

Features and behaviors that apply across multiple screens (navigation, theming, maps,
real-time updates, etc.).

- _(fill in)_

---

## 3. Mobile App — Field Worker Companion

The mobile app is the field-facing surface used by drivers and workers on the job.

### 3.1 Authentication & Session

- _(fill in)_

### 3.2 Home / Today's Work

- _(fill in)_

### 3.3 Job / Order Details

- _(fill in)_

### 3.4 Navigation & Live Location

- _(fill in)_

### 3.5 Order History

- _(fill in)_

### 3.6 Profile & Ratings

- _(fill in)_

### 3.7 Notifications

- _(fill in)_

---

## 4. Shared Concepts

Concepts that show up on both surfaces and are worth defining once (e.g. what a *route plan*
is, what a *job/order* is, what the worker statuses mean).

- **_(term)_** — _(fill in)_
- **_(term)_** — _(fill in)_

---

## 5. Legend

Optional status markers you can use next to any feature while filling this in — delete this
section if you don't need it.

| Marker        | Meaning                                  |
|---------------|------------------------------------------|
| ✅ Done        | Implemented and working                  |
| 🚧 In progress | Partially built                          |
| 📋 Planned     | Designed / intended, not yet built       |

---

*Fill in the bullets above. Keep descriptions user-facing and concise; link to source files
only where it genuinely helps a reader locate the screen.*
