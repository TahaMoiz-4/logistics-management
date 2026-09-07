# Address Search with Photon

> **Purpose.** How address search works, why it is built this way, and what to do
> to add it to another form (customers, depots, anything else that owns a
> `Location`). Written so the next person does not have to re-derive the
> reasoning — or repeat the mistakes.

---

## 1. The problem

An order needs a location. Before this, the dispatcher typed raw coordinates
into two number fields:

```
Latitude   [ 24.8607 ]
Longitude  [ 67.0011 ]
```

That is fine for a developer and unusable for a dispatcher. Nobody knows the
decimal coordinates of a house in Gulshan. It also left `Location.address_text`
empty, so every order in every list read as a pair of numbers.

The goal: type an address, pick it from a list, get coordinates.

---

## 2. Why Photon

[Photon](https://github.com/komoot/photon) is a search-as-you-type geocoder over
OpenStreetMap data, built by Komoot. It suits this project because:

* **Same data as the router.** The routing graph is OSM (via OSMnx). A geocoder
  over the same source will not suggest a place the router has never heard of.
* **Built for autocomplete.** Elasticsearch prefix matching, designed to be hit
  on every keystroke — unlike Nominatim, which is a batch geocoder and asks you
  not to.
* **Good Karachi coverage.** Verified against the live API: neighbourhoods,
  landmarks, hospitals and named streets all resolve correctly.
* **Free, no API key.** We call Komoot's public instance.

### The cost of the public instance

No API key, no published quota, and Komoot ask that you not bulk-geocode. Two
things keep us within acceptable use:

1. **Client-side debounce** (250 ms) — a 16-character address is ~1 request, not
   16.
2. **Server-side Redis cache** — dispatchers in one city search the same
   neighbourhoods constantly, so the hit rate is high.

If usage ever grows past that, the fix is to self-host Photon and point
`PHOTON_BASE_URL` at it. Nothing else changes.

---

## 3. Architecture

```
Browser                       FastAPI                        Photon
───────                       ───────                        ──────
AddressSearch.tsx
  │  types "askari"
  │
useAddressSearch.ts
  │  debounce 250ms
  │  React Query (cache + abort)
  │
  └── GET /v1/geocode/search?q=…
                    │
              api/v1/geocode.py
                    │  auth (same Bearer flow as every endpoint)
                    │
              services/photon.py
                    │  Redis cache lookup ──── hit ──► return
                    │  miss:
                    │  + bbox            ─────────────► GET /api?q=…&bbox=…
                    │  + lat/lon bias                    (Komoot public)
                    │  + lang=en          ◄───────────── GeoJSON
                    │
                    │  filter: polygon contains?
                    │  dedupe, compose labels
                    │
              maps.py snap_distance_m
                    │  routable? (KD-tree over road graph)
                    ▼
              {label, context, address_text, lat, lng, routable, …}
```

### Why a backend proxy instead of calling Photon from the browser

* The service-area filter is **policy**, not a UI concern. Enforced server-side,
  no client can bypass it.
* Keeps every call inside the existing Bearer-token flow.
* One place to cache, and one line to change when self-hosting.
* No CORS.

---

## 4. Keeping search and routing in sync

This is the part worth understanding before changing anything.

The routing graph is built from a place name:

```python
ox.graph_from_place(settings.MAP_PLACE, network_type="drive")   # maps.py
```

The geocoder's service area is derived from **the same setting**, via the same
call `graph_from_place` makes internally:

```python
ox.geocode_to_gdf(settings.MAP_PLACE)                           # boundary.py
```

So `MAP_PLACE` is the single source of truth. Change it and the router and the
search box move together — search can never offer a location the router cannot
reach.

> ⚠️ **`GRAPH_CACHE_KEY` in `maps.py` does not encode the place name.** If you
> change `MAP_PLACE`, bump that key too, or Redis will serve the old city's
> graph. This is deliberate — auto-deriving it would silently invalidate an
> ~80 MB cache on any edit — but it is a manual step you must remember.

### Two levels of filtering, and why both exist

| | What | Where | Cost |
|---|---|---|---|
| **bbox** | rectangle around the service area | sent to Photon, filtered server-side by Photon | one URL param |
| **polygon** | the real administrative shape | `boundary.is_inside()` on each result | one shapely `contains` per point |

Photon's only geographic parameter is `bbox`, and it is a **hard filter**, not a
bias — verified: with the Karachi bbox, `q=eiffel tower` returns only Bahria
Town's replica, and `q=lahore` returns no Lahore results.

But a bbox is loose. For Karachi Division the polygon is 0.52 deg² while its
bounding box is 1.62 deg² — **about two-thirds of the rectangle is sea and
desert.** So the bbox is the cheap network-level filter and the polygon check is
the actual correctness guarantee.

**`lat`/`lon` are also sent** as a soft distance bias toward the service-area
centroid. Unlike bbox, this only reranks — it pushes central results above
equally-good matches at the edge.

---

## 5. Label composition

Photon returns a loose, inconsistent property bag. Fields are **omitted**, not
nulled, and Karachi's admin boundaries are often tagged in Urdu.

The rule (`photon.py::_primary_label` / `_secondary_label`):

```
Askari IV Mosque              ← primary:   name, else "housenumber street"
Rashid Minhas Road, Gulshan   ← secondary: street, locality, district
```

* **`city` is deliberately excluded.** Every result is inside the service area by
  construction, so "Karachi" on every row is noise. This also dodges most of the
  script problem: `city` and `district` are frequently Urdu (`کراچی`), while
  `name` and `street` are usually Latin.
* **`lang=en` is requested**, which helps more than expected — `district` comes
  back as "Gulshan-e-Iqbal" rather than `گلشن اقبال` where an English tag exists.
  It is not a guarantee; some Urdu still leaks through, and that is accepted.
* Results are **deduped on (label, rounded lat/lng)** because OSM frequently
  holds the same place as both a node and a way.

`address_text` is `"label, context"` flattened — that is what gets persisted to
`Location.address_text`.

---

## 6. Routability

A geocoded point can be inside the service area but far from any drivable road.
If that gets saved, the matrix builder returns `PENALTY_SEC` for every pair and
ALNS silently leaves the order unserved — with no explanation anywhere.

So each result is annotated:

```json
{ "routable": true, "snap_distance_m": 31.6 }
```

* `routable: false` → farther than `GEOCODE_MAX_SNAP_M` (500 m) from a road.
  Shown **greyed out and unselectable** with a plain-language message, not
  hidden — a dispatcher may know a place OSM does not, and silently dropping a
  result they can see on a map is confusing.
* `routable: null` → the road graph was not loaded, so we **could not check**.
  Distinct from `false`. The console shows no warning in this case.

### The performance trap

`ox.nearest_nodes()` rebuilds a KD-tree over **all 178,356 nodes on every call**.
Checking a page of 8 results cost ~2.2 s per keystroke.

`maps.py` now caches the tree (`_get_node_tree`) — the graph is read-only after
loading, so there is no reason to rebuild. Same answers, ~0.0003 s for 8 results.

**If you call `nearest_nodes` anywhere else in a loop, you will hit this.** Pass
an array of points, or use the cached tree.

---

## 7. Failure behaviour

An autocomplete that throws is worse than one that shows nothing. Everything
degrades quietly:

| Failure | Behaviour |
|---|---|
| Photon down / timeout | empty result list, warning logged |
| Malformed JSON | empty result list |
| Redis unavailable | cache silently skipped, still works |
| Boundary unavailable | **fails open** — unfiltered results, rather than rejecting everything |
| Road graph not loaded | `routable: null`, no warning shown |

The road graph and boundary are warmed by a **lifespan handler in `main.py`**,
and both loads are best-effort — a cold graph download takes minutes and must
never block startup or fail a health check.

> Seed Redis so startup is a fast unpickle rather than a download:
> `docker compose exec backend python -m src.utils.scripts.seed_graph`

---

## 8. Frontend mechanics

The "search per keystroke" feel comes from three separate things:

1. **Debounce (250 ms)** — collapses a burst of typing into one request. The
   cleanup return in the `useEffect` is what makes it a debounce rather than a
   delay; without it every keystroke still fires, just later.
2. **React Query keyed on the search term** — this is what fixes out-of-order
   responses. Because `["geocode","ask"]` and `["geocode","aska"]` are separate
   cache entries, a late response for "ask" lands under its own key and cannot
   overwrite the fresher one. (An `AbortSignal` is also passed, but its job is
   cancelling wasted requests to Komoot, not preventing corruption.)
3. **Caching** — backspacing is instant, zero requests.

FastAPI's side is a plain stateless GET. No websockets, no SSE — they are not
needed here.

---

## 9. Adding address search to another form

Customers and depots both create `Location` rows through `LocationRepository`,
so the backend already accepts `lat` / `lng` / `address_text` on
`CustomerCreate`, `CustomerUpdate`, `DepotCreate` and `DepotUpdate`.

**No backend work is required.** The steps are:

1. Import the component:
   ```tsx
   import { AddressSearch, type SelectedAddress } from "@/components/address/AddressSearch";
   ```
2. Hold the picked address in state:
   ```tsx
   const [address, setAddress] = useState<SelectedAddress | null>(null);
   ```
3. Render it, keeping manual lat/lng as a collapsed fallback (see
   `NewOrderForm.tsx` for the pattern — informal Karachi addresses are often not
   in OSM, so manual entry must stay reachable).
4. Send `lat`, `lng` **and** `address_text` in the create/update body.

### What is NOT built yet

The console currently has **no create/edit forms for customers or depots at
all** — customers appear only as a dropdown in the order form, and depots are
read-only on the Fleet page. Adding address search there means building those
forms first. The backend CRUD exists and is ready.

### A known modelling wart

An order today collects its own address, even when the customer already has a
saved one. The customer's location is used only as a *prefill*. For a
field-service business the customer's address is usually the right answer, and
the order should only override it for a one-off visit elsewhere. Worth
revisiting when customer management is built — it would remove a step from the
most common path.

---

## 10. Configuration reference

| Setting | Default | Notes |
|---|---|---|
| `MAP_PLACE` | `Karachi, Pakistan` | **Shared with the routing graph.** Bump `GRAPH_CACHE_KEY` if changed. |
| `PHOTON_BASE_URL` | `https://photon.komoot.io` | Point at a self-hosted instance to drop the fair-use constraint. |
| `PHOTON_TIMEOUT_SEC` | `4.0` | |
| `GEOCODE_RESULT_LIMIT` | `8` | Photon is over-fetched at 2× this, since the polygon filter discards some. |
| `GEOCODE_CACHE_TTL_SEC` | `86400` | |
| `GEOCODE_MAX_SNAP_M` | `500.0` | Past this from a road, a result is flagged unroutable. |

> **Historical note.** `PHOTON_BASE_URL` was originally declared as
> `PHOTON_BASE_URL=""` with no type annotation. pydantic-settings builds its
> field list from `__annotations__`, so it was never a settings field at all and
> the `.env` value was silently ignored, with no error. Every setting in
> `config.py` needs an annotation.

---

## 11. Files

| File | Role |
|---|---|
| `src/services/photon.py` | Photon client: bbox, bias, labels, dedupe, cache |
| `src/services/boundary.py` | `MAP_PLACE` → bbox + polygon, Redis-cached |
| `src/api/v1/geocode.py` | `GET /v1/geocode/search` |
| `src/schemas/geocode.py` | Response contract |
| `src/services/maps.py` | `peek_graph`, `snap_distance_m` (cached KD-tree) |
| `frontend/src/components/address/AddressSearch.tsx` | The dropdown |
| `frontend/src/components/address/useAddressSearch.ts` | Debounce + query |
