/**
 * Hand-mirrored types for the backend contract (documentation/openapi.json).
 *
 * These are kept in sync with the FastAPI schemas by hand for now. When the
 * surface grows we can codegen from openapi.json, but explicit types keep the
 * early screens readable and reviewable.
 */

export interface SysUser {
  id: number;
  username: string;
  role: string;
  company_id: number;
  contact_email: string | null;
  contact_number: string | null;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: SysUser;
}

export interface OrderStatusCounts {
  pending: number;
  assigned: number;
  in_transit: number;
  delivered: number;
  failed: number;
}

export interface PlanStatusCounts {
  draft: number;
  optimizing: number;
  ready: number;
  dispatched: number;
  completed: number;
  failed: number;
}

// ---------- meta ----------
export interface MetaEnums {
  order_status: string[];
  order_priority: string[];
  plan_status: string[];
  route_status: string[];
  stop_type: string[];
  worker_stop_status: string[];
  vehicle_type: string[];
  fuel_type: string[];
  operational_status: string[];
  service_type: string[];
  device_platform: string[];
  nurse_skills: string[];
  technician_skills: string[];
  /** The company's own service type ("nurse" | "technician"). */
  company_service_type: string;
  /** Skills applicable to this company (nurse or tech set). */
  applicable_skills: string[];
}

// ---------- customers ----------
export interface Customer {
  id: number;
  name: string;
  company_id: number;
  contact_email: string | null;
  contact_phone: string | null;
  location_id: number | null;
  lat: number | null;
  lng: number | null;
  address_text: string | null;
  order_count: number;
}

// ---------- settings / demo tooling ----------
export interface DemoDataStatus {
  /** DEMO_TOOLS_ENABLED on this deployment. */
  enabled: boolean;
  is_admin: boolean;
}

export interface ReseedDemoDataResponse {
  removed_rows: number;
  orders: number;
  customers: number;
  employees: number;
}

// ---------- geocoding ----------
/** One suggestion from /v1/geocode/search. See src/services/photon.py. */
export interface GeocodeResult {
  /** Bold first line — the POI/street name, or "housenumber street". */
  label: string;
  /** Muted second line — street/locality/district. May be empty. */
  context: string;
  /** Flattened "label, context", persisted to Location.address_text. */
  address_text: string;
  lat: number;
  lng: number;
  type: string | null; // house | street | locality | district | city
  osm_id: number | null;
  osm_type: string | null;
  postcode: string | null;
  /**
   * Whether the point sits near a drivable road. null means the backend could
   * NOT check (road graph not loaded) — distinct from false, which means it
   * checked and the place is outside the routable network.
   */
  routable: boolean | null;
  snap_distance_m: number | null;
}

export interface GeocodeSearchOut {
  query: string;
  results: GeocodeResult[];
}

// ---------- orders ----------
export interface Order {
  id: number;
  name: string | null;
  company_id: number;
  customer_id: number;
  customer_name: string | null;
  customer_phone: string | null;
  location_id: number | null;
  lat: number | null;
  lng: number | null;
  address_text: string | null;
  status: string;
  priority: string;
  service_date: string | null;
  timewindow_start: string | null;
  timewindow_end: string | null;
  service_duration_min: number | null;
  required_nurse_skills: string[];
  required_tech_skills: string[];
  weight_kg: number | null;
  volume_m3: number | null;
  notes: string | null;
  created_at: string | null;
}

export interface OrderCreate {
  customer_id: number;
  service_date: string;
  location_id?: number | null;
  lat?: number | null;
  lng?: number | null;
  address_text?: string | null;
  name?: string | null;
  priority?: string | null;
  timewindow_start?: string | null;
  timewindow_end?: string | null;
  service_duration_min?: number | null;
  required_skills?: string[];
  weight_kg?: number | null;
  volume_m3?: number | null;
  notes?: string | null;
}

export interface OrderUpdate {
  name?: string | null;
  status?: string | null;
  priority?: string | null;
  service_date?: string | null;
  lat?: number | null;
  lng?: number | null;
  address_text?: string | null;
  timewindow_start?: string | null;
  timewindow_end?: string | null;
  service_duration_min?: number | null;
  required_skills?: string[] | null;
  weight_kg?: number | null;
  volume_m3?: number | null;
  notes?: string | null;
}

// ---------- servable orders (plan picker) ----------
// NOTE: the /orders/servable payload differs from the full OrderOut — it exposes
// a single `required_skills` array (not the nurse/tech split) and has no
// customer_name, only `name`.
export interface ServableOrder {
  id: number;
  name: string | null;
  customer_id: number;
  address_text: string | null;
  service_date: string | null;
  status: string;
  priority: string;
  required_skills: string[];
  timewindow_start: string | null;
  timewindow_end: string | null;
  service_duration_min: number | null;
  lat: number | null;
  lng: number | null;
}

// ---------- route plans ----------
export interface RoutePlanSummary {
  id: number;
  company_id: number;
  depot_id: number;
  planned_date: string;
  status: string;
  name: string | null;
  objective_value: number | null;
  total_orders: number | null;
  total_routes: number | null;
  total_unserved: number | null;
  optimized_at: string | null;
  created_at: string | null;
}

export interface CreateRoutePlanRequest {
  depot_id?: number | null;
  order_ids?: number[] | null;
  planned_date?: string | null;
  name?: string | null;
  repair_mode: string;
  config_overrides?: Record<string, unknown> | null;
}

export interface CreateRoutePlanResponse {
  route_plan_id: number;
  status: string;
  planned_date: string;
  order_count: number;
  stream_url: string;
}

export interface ApproveResponse {
  route_plan_id: number;
  status: string;
  orders_assigned?: number;
  workers_notified?: number;
  [k: string]: unknown;
}

// ---------- solver progress (SSE) ----------
export interface ProgressEvent {
  event: string;
  message?: string;
  iteration?: number;
  current_objective?: number | null;
  best_objective?: number | null;
  elapsed_sec?: number;
}

// ---------- map data (Leaflet) ----------
export interface MapDepot {
  location_id: number;
  lat: number;
  lng: number;
}
export interface MapOrderMarker {
  order_id: number;
  lat: number;
  lng: number;
  served: boolean;
  worker_id: number | null;
}
export interface MapRoutePoint {
  seq: number;
  stop_type: string;
  lat: number;
  lng: number;
}
/** GeoJSON MultiLineString: coordinates are [lng, lat] pairs. */
export interface GeoMultiLineString {
  type: "MultiLineString";
  coordinates: number[][][];
}
export interface MapDriverRoute {
  driver_route_id: number;
  driver_id: number | null;
  driver_name: string | null;
  vehicle_id: number;
  vehicle_plate: string | null;
  total_distance_m: number | null;
  total_time_sec: number | null;
  points: MapRoutePoint[];
  geometry: GeoMultiLineString | null;
}
export interface MapDataOut {
  depot: MapDepot;
  driver_routes: MapDriverRoute[];
  order_markers: MapOrderMarker[];
}

// ---------- diagnostics ----------
export interface DiagnosticsSummary {
  initial_objective: number;
  best_objective: number;
  improvement_pct: number;
  iterations: number;
  runtime_sec: number;
  iters_per_sec: number;
  total_orders: number;
  total_assigned: number;
  total_unserved: number;
  workers_used: number;
  workers_idle: number;
}
export interface IterationTrace {
  objectives: number[];
  best_so_far: number[];
  runtimes: number[];
  num_iterations: number;
}
/** operator_stats: { destroy: {opName: {...}}, repair: {...}, outcome_legend: [...] } */
export interface DiagnosticsOut {
  summary: DiagnosticsSummary;
  cost_breakdown: Record<string, number>;
  penalties_used: Record<string, number>;
  unserved: UnservedOrder[];
  iteration_trace: IterationTrace | null;
  operator_stats: Record<string, unknown> | null;
}

export interface UnservedOrder {
  order_id: number;
  reason: string;
}

// ---------- driver routes / worker assignments ----------
export interface DriverStop {
  sequence_number: number;
  stop_type: string;
  location_id: number;
  lat: number | null;
  lng: number | null;
  eta: string | null;
  etd: string | null;
  distance_from_prev_m: number | null;
  time_from_prev_sec: number | null;
}
export interface DriverRoute {
  id: number;
  driver_id: number | null;
  vehicle_id: number;
  status: string;
  total_distance_m: number | null;
  total_time_sec: number | null;
  stops: DriverStop[];
}
export interface WorkerStop {
  sequence_number: number;
  order_id: number;
  lat: number | null;
  lng: number | null;
  service_start_estimated: string | null;
  service_end_estimated: string | null;
}
export interface WorkerAssignment {
  id: number;
  worker_id: number;
  worker_type: string;
  worker_name?: string | null;
  stops: WorkerStop[];
}

// ---------- fleet ----------
export interface Vehicle {
  id: number;
  company_id: number;
  depot_id: number | null;
  depot_name: string | null;
  license_plate: string;
  type: string;
  model: string | null;
  color: string | null;
  seating_capacity: number | null;
  max_weight_kg: number | null;
  max_volume_m3: number | null;
  avg_speed_kmh: number | null;
  fuel_type: string | null;
  fuel_average: number | null;
  operational_status: string | null;
  assigned_driver_id: number | null;
}

export interface Driver {
  id: number;
  company_id: number;
  employee_id: number | null;
  name: string | null;
  contact_number: string | null;
  contact_email: string | null;
  drivers_license_number: string | null;
  skills: string[];
  rating: number | null;
  kms_driven: number | null;
  orders_completed: number | null;
  operational_status: string | null;
  unavailable_reason: string | null;
  vehicle_id: number | null;
  vehicle_plate: string | null;
}

export interface Depot {
  id: number;
  name: string;
  company_id: number;
  operational_status: string | null;
  location_id: number | null;
  lat: number | null;
  lng: number | null;
  address_text: string | null;
}

// ---------- workers ----------
export interface Worker {
  id: number;
  worker_type: string;
  employee_id: number | null;
  name: string | null;
  contact_number: string | null;
  contact_email: string | null;
  skills: string[];
  rating: number | null;
  orders_completed: number | null;
  operational_status: string | null;
  unavailable_reason: string | null;
  shift_start: string | null;
  shift_end: string | null;
}

// ---------- live tracking ----------
export interface LivePosition {
  subject_type: string; // "nurse" | "technician" | "driver" | "vehicle"
  subject_id: number;
  name: string | null;
  lat: number;
  lng: number;
  recorded_at: string;
  employee_id: number | null;
  employee_code: string | null;
  contact_number: string | null;
  seconds_ago: number;
  is_stale: boolean;
}
export interface LiveTrackingOut {
  positions: LivePosition[];
  as_of: string;
  stale_after_sec: number;
}

export interface AvailabilityRosterEntry {
  employee_id: number;
  name: string;
  role: string;
  contact_number: string | null;
  contact_email: string | null;
  operational_status: string;
  available: boolean;
  unavailable_reason: string | null;
  since: string | null;
}

export interface DashboardToday {
  date: string;
  orders_today: number;
  order_status_counts: OrderStatusCounts;
  completion_pct: number;
  plans_today: number;
  plan_status_counts: PlanStatusCounts;
  workers_total: number;
  workers_available: number;
  workers_unavailable: number;
  drivers_total: number;
  vehicles_total: number;
}
