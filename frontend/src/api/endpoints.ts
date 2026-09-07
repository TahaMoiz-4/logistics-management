/**
 * Typed endpoint functions — the ONLY way UI/query code reaches the backend.
 * One function per API operation, grouped by resource.
 */
import { request } from "./client";
import type {
  ApproveResponse,
  AvailabilityRosterEntry,
  CreateRoutePlanRequest,
  CreateRoutePlanResponse,
  Customer,
  DashboardToday,
  Depot,
  DiagnosticsOut,
  Driver,
  GeocodeSearchOut,
  DriverRoute,
  LiveTrackingOut,
  LoginRequest,
  LoginResponse,
  MapDataOut,
  MetaEnums,
  Order,
  OrderCreate,
  OrderUpdate,
  RoutePlanSummary,
  ServableOrder,
  SysUser,
  UnservedOrder,
  Vehicle,
  Worker,
  WorkerAssignment,
} from "./types";

export const authApi = {
  login: (body: LoginRequest) =>
    request<LoginResponse>("/v1/auth/login", { method: "POST", body, anonymous: true }),
  logout: () => request<void>("/v1/auth/logout", { method: "POST" }),
  me: () => request<SysUser>("/v1/auth/me"),
};

export const dashboardApi = {
  today: () => request<DashboardToday>("/v1/dashboard/today"),
};

export const metaApi = {
  enums: () => request<MetaEnums>("/v1/meta/enums"),
};

export const geocodeApi = {
  /**
   * Address autocomplete. Called on every (debounced) keystroke, so it takes an
   * AbortSignal: without one, a slow response for "ask" can land after the
   * response for "aska" and overwrite fresher results.
   */
  search: (q: string, signal?: AbortSignal) =>
    request<GeocodeSearchOut>(`/v1/geocode/search?q=${encodeURIComponent(q)}`, { signal }),
};

export const trackingApi = {
  live: () => request<LiveTrackingOut>("/v1/tracking/live"),
  availability: () => request<AvailabilityRosterEntry[]>("/v1/tracking/availability"),
};

export const customersApi = {
  list: () => request<Customer[]>("/v1/customers"),
};

export const vehiclesApi = {
  list: () => request<Vehicle[]>("/v1/vehicles"),
};

export const driversApi = {
  list: () => request<Driver[]>("/v1/drivers"),
};

export const depotsApi = {
  list: () => request<Depot[]>("/v1/depots"),
};

export const workersApi = {
  list: () => request<Worker[]>("/v1/workers"),
};

export const ordersApi = {
  list: () => request<Order[]>("/v1/orders"),
  servable: () => request<ServableOrder[]>("/v1/orders/servable"),
  get: (id: number) => request<Order>(`/v1/orders/${id}`),
  create: (body: OrderCreate) => request<Order>("/v1/orders", { method: "POST", body }),
  update: (id: number, body: OrderUpdate) =>
    request<Order>(`/v1/orders/${id}`, { method: "PUT", body }),
  remove: (id: number) => request<void>(`/v1/orders/${id}`, { method: "DELETE" }),
};

export const routePlansApi = {
  list: () => request<RoutePlanSummary[]>("/v1/route-plans"),
  get: (id: number) => request<RoutePlanSummary>(`/v1/route-plans/${id}`),
  create: (body: CreateRoutePlanRequest) =>
    request<CreateRoutePlanResponse>("/v1/route-plans", { method: "POST", body }),
  remove: (id: number) => request<void>(`/v1/route-plans/${id}`, { method: "DELETE" }),
  approve: (id: number) =>
    request<ApproveResponse>(`/v1/route-plans/${id}/approve`, { method: "POST" }),
  mapData: (id: number) => request<MapDataOut>(`/v1/route-plans/${id}/map-data`),
  diagnostics: (id: number) => request<DiagnosticsOut>(`/v1/route-plans/${id}/diagnostics`),
  driverRoutes: (id: number) => request<DriverRoute[]>(`/v1/route-plans/${id}/driver-routes`),
  workerAssignments: (id: number) =>
    request<WorkerAssignment[]>(`/v1/route-plans/${id}/worker-assignments`),
  unserved: (id: number) => request<UnservedOrder[]>(`/v1/route-plans/${id}/unserved`),
};
