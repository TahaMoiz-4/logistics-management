/**
 * Solved plan detail — the result of an optimization:
 *   - summary banner (objective / improvement / served / routes) + Approve
 *   - Leaflet route map with a per-driver legend (tap to isolate)
 *   - unserved-orders alert
 *   - driver-routes & nurse-assignment tables
 *   - full solver diagnostics
 *
 * If the plan is still optimizing, we bounce to the live view.
 */
import { useState, type CSSProperties } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePageMeta } from "@/components/shell/pageMeta";
import { Icon } from "@/components/Icon";
import { Spinner } from "@/components/Spinner";
import { RouteMap, routeColor } from "@/components/map/RouteMap";
import { Diagnostics } from "./Diagnostics";
import { usePlan, usePlanResults } from "./usePlans";
import { routePlansApi } from "@/api/endpoints";
import { useToast } from "@/components/Toast";
import { ApiError } from "@/api/client";
import type { MapDriverRoute, WorkerAssignment } from "@/api/types";
import { colors, font, radius, shadow } from "@/theme/tokens";

export function PlanDetailPage() {
  const { id } = useParams();
  const planId = Number(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();

  const { data: plan, isLoading } = usePlan(planId, { refetchInterval: false });
  usePageMeta(plan?.name ?? `Plan PLN-${planId}`, plan ? `Planned ${plan.planned_date}` : "Route plan");

  const isOptimizing = plan?.status === "optimizing" || plan?.status === "draft";
  const results = usePlanResults(planId, !!plan && !isOptimizing);
  const [highlight, setHighlight] = useState<number | null>(null);

  const approve = useMutation({
    mutationFn: () => routePlansApi.approve(planId),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["route-plans"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      const n = res.workers_notified;
      toast.show(
        `Plan dispatched${n != null ? ` · ${n} worker${n === 1 ? "" : "s"} notified` : ""}`,
      );
    },
    onError: (err) => toast.show(err instanceof ApiError ? err.message : "Approval failed."),
  });

  if (isLoading || !plan) {
    return (
      <div style={centerBox}>
        <Spinner size={26} />
      </div>
    );
  }

  if (isOptimizing) {
    return (
      <div style={centerBox}>
        <div style={{ textAlign: "center" }}>
          <div style={{ marginBottom: 14, color: colors.textMuted }}>This plan is still optimizing.</div>
          <button style={darkBtn} onClick={() => navigate(`/plans/${planId}/live`)}>
            Watch the solver
          </button>
        </div>
      </div>
    );
  }

  const { mapData, diagnostics, workerAssignments, unserved } = results;
  const canApprove = plan.status === "ready";
  const dispatched = plan.status === "dispatched" || plan.status === "completed";

  const improvement = diagnostics.data?.summary.improvement_pct;
  const served = diagnostics.data
    ? `${diagnostics.data.summary.total_assigned} / ${diagnostics.data.summary.total_orders}`
    : `${(plan.total_orders ?? 0) - (plan.total_unserved ?? 0)} / ${plan.total_orders ?? 0}`;

  // Authoritative set of orders that actually belong to this plan (served via
  // worker assignments + officially unserved). Used to filter out stray markers
  // the /map-data endpoint may include from other plans/dates.
  const planOrderIds =
    workerAssignments.data && unserved.data
      ? new Set<number>([
          ...workerAssignments.data.flatMap((w) => w.stops.map((s) => s.order_id)),
          ...unserved.data.map((u) => u.order_id),
        ])
      : undefined;

  return (
    <div className="ng-fade" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* banner */}
      <div style={banner}>
        <div style={{ flex: 1, display: "flex", gap: 32, flexWrap: "wrap" }}>
          <Metric label="Objective" value={plan.objective_value != null ? Math.round(plan.objective_value).toLocaleString() : "—"} />
          <Metric label="Improved" value={improvement != null ? `↓ ${improvement.toFixed(1)}%` : "—"} />
          <Metric label="Served" value={served} />
          <Metric label="Routes" value={String(plan.total_routes ?? "—")} />
        </div>
        {dispatched ? (
          <div style={dispatchedTag}>
            <Icon name="check" size={16} />
            <span>Dispatched</span>
          </div>
        ) : (
          <button
            style={approveBtn(canApprove && !approve.isPending)}
            disabled={!canApprove || approve.isPending}
            onClick={() => approve.mutate()}
          >
            {approve.isPending ? (
              <Spinner size={16} color="#fff" track="rgba(255,255,255,.4)" />
            ) : (
              <Icon name="check" size={18} />
            )}
            Approve &amp; Dispatch
          </button>
        )}
      </div>

      {/* map + legend */}
      <div style={mapGrid}>
        <div style={mapCard}>
          {mapData.isLoading && (
            <div style={mapLoading}>
              <Spinner size={24} />
            </div>
          )}
          {mapData.isError && (
            <div style={mapLoading}>
              <span style={{ color: colors.textMuted }}>Couldn't load the map.</span>
            </div>
          )}
          {mapData.data && (
            <RouteMap
              data={mapData.data}
              highlightRouteId={highlight}
              height={460}
              orderFilter={planOrderIds}
            />
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={legendEyebrow}>Driver routes · tap to isolate</div>
          {mapData.data?.driver_routes.map((r, i) => (
            <LegendRow
              key={r.driver_route_id}
              route={r}
              color={routeColor(i)}
              active={highlight === r.driver_route_id}
              onClick={() =>
                setHighlight((h) => (h === r.driver_route_id ? null : r.driver_route_id))
              }
            />
          ))}
          <div style={mapKey}>
            <div style={keyRow}>
              <span style={{ width: 13, height: 13, background: colors.ink, borderRadius: 3, transform: "rotate(45deg)" }} />
              Depot
            </div>
            <div style={keyRow}>
              <span style={{ width: 13, height: 13, borderRadius: "50%", border: `2px solid ${colors.ink}`, background: "#fff" }} />
              Served order
            </div>
            <div style={keyRow}>
              <span style={{ width: 13, height: 13, borderRadius: "50%", border: "2px dashed #b42318" }} />
              Unserved order
            </div>
          </div>
        </div>
      </div>

      {/* unserved alert */}
      {unserved.data && unserved.data.length > 0 && (
        <div style={unservedCard}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, fontWeight: 700, fontSize: 14 }}>
            Unserved orders · {unserved.data.length}
          </div>
          <div style={{ fontSize: 12, color: colors.textMuted, marginTop: 4, marginBottom: 14 }}>
            The solver could not place these. Resolve before dispatch.
          </div>
          {unserved.data.map((u) => (
            <div key={u.order_id} style={unservedRow}>
              <span style={{ fontFamily: font.mono, fontSize: 12, fontWeight: 700 }}>ORD-{u.order_id}</span>
              <span style={reasonChip}>{u.reason.replace(/_/g, " ")}</span>
            </div>
          ))}
        </div>
      )}

      {/* tables */}
      <div style={tableGrid}>
        <div style={tableCard}>
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>Driver routes</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {mapData.data?.driver_routes.map((r) => (
              <div key={r.driver_route_id} style={driverBox}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>
                    {r.driver_name ?? r.vehicle_plate ?? `Route ${r.driver_route_id}`}
                  </span>
                  <span style={{ fontFamily: font.mono, fontSize: 11, color: colors.textMuted }}>
                    {fmtKm(r.total_distance_m)} · {fmtMin(r.total_time_sec)}
                  </span>
                </div>
                <div style={{ fontFamily: font.mono, fontSize: 11, color: "#9a9a95", marginTop: 8 }}>
                  {r.vehicle_plate ?? "—"} · {r.points.filter((p) => p.stop_type !== "depot_start" && p.stop_type !== "depot_end").length} stops
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={tableCard}>
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>Nurse assignments</div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            {workerAssignments.data?.length === 0 && (
              <div style={{ fontSize: 13, color: colors.textFaint }}>No assignments.</div>
            )}
            {workerAssignments.data?.map((w) => (
              <WorkerRow key={w.id} w={w} />
            ))}
          </div>
        </div>
      </div>

      {/* diagnostics */}
      {diagnostics.data && <Diagnostics diag={diagnostics.data} />}
      {diagnostics.isLoading && (
        <div style={{ ...tableCard, display: "flex", justifyContent: "center", padding: 40 }}>
          <Spinner size={22} />
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={metricLabel}>{label}</div>
      <div style={metricValue}>{value}</div>
    </div>
  );
}

function LegendRow({
  route,
  color,
  active,
  onClick,
}: {
  route: MapDriverRoute;
  color: string;
  active: boolean;
  onClick: () => void;
}) {
  const stops = route.points.filter(
    (p) => p.stop_type !== "depot_start" && p.stop_type !== "depot_end",
  ).length;
  return (
    <div onClick={onClick} style={legendRow(active)}>
      <span style={{ width: 14, height: 14, borderRadius: 4, background: color, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 13 }}>
          {route.driver_name ?? route.vehicle_plate ?? `Route ${route.driver_route_id}`}
        </div>
        <div style={{ fontFamily: font.mono, fontSize: 11, color: "#9a9a95" }}>
          {route.vehicle_plate ?? "—"} · {stops} stops
        </div>
      </div>
      <div style={{ textAlign: "right", fontFamily: font.mono, fontSize: 11, color: colors.textMuted }}>
        <div>{fmtKm(route.total_distance_m)}</div>
        <div>{fmtMin(route.total_time_sec)}</div>
      </div>
    </div>
  );
}

function WorkerRow({ w }: { w: WorkerAssignment }) {
  const seq = w.stops.map((s) => `ORD-${s.order_id}`).join(" → ");
  return (
    <div style={workerRow}>
      <span style={workerBadge}>{w.stops.length}</span>
      <span style={{ fontWeight: 500, fontSize: 13, flex: 1 }}>
        {w.worker_type === "nurse" ? "Nurse" : "Tech"} #{w.worker_id}
      </span>
      <span style={{ fontFamily: font.mono, fontSize: 11, color: "#9a9a95", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {seq}
      </span>
    </div>
  );
}

function fmtKm(m: number | null): string {
  if (m == null) return "—";
  return `${(m / 1000).toFixed(1)} km`;
}
function fmtMin(sec: number | null): string {
  if (sec == null) return "—";
  return `${Math.round(sec / 60)} min`;
}

// ---- styles ----
const centerBox: CSSProperties = { minHeight: 300, display: "flex", alignItems: "center", justifyContent: "center" };
const darkBtn: CSSProperties = {
  height: 44,
  padding: "0 20px",
  border: "none",
  borderRadius: radius.md,
  background: colors.ink,
  color: colors.inkOnDark,
  fontWeight: 600,
  cursor: "pointer",
};
const banner: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.xl,
  padding: "20px 24px",
  display: "flex",
  alignItems: "center",
  gap: 24,
};
const metricLabel: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 10,
  letterSpacing: ".06em",
  textTransform: "uppercase",
  color: "#a0a09a",
};
const metricValue: CSSProperties = { fontFamily: font.mono, fontSize: 24, fontWeight: 700, marginTop: 4 };
function approveBtn(enabled: boolean): CSSProperties {
  return {
    height: 50,
    padding: "0 26px",
    border: "none",
    borderRadius: radius.lg,
    background: colors.accent,
    color: "#fff",
    fontSize: 15,
    fontWeight: 700,
    cursor: enabled ? "pointer" : "default",
    opacity: enabled ? 1 : 0.5,
    display: "flex",
    alignItems: "center",
    gap: 10,
    boxShadow: enabled ? shadow.accent : "none",
  };
}
const dispatchedTag: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  height: 50,
  padding: "0 22px",
  borderRadius: radius.lg,
  background: colors.ink,
  color: colors.inkOnDark,
  fontSize: 14,
  fontWeight: 700,
};
const mapGrid: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 300px", gap: 20 };
const mapCard: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.xl,
  overflow: "hidden",
  height: 460,
};
const mapLoading: CSSProperties = { height: "100%", display: "flex", alignItems: "center", justifyContent: "center" };
const legendEyebrow: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 10,
  letterSpacing: ".06em",
  textTransform: "uppercase",
  color: "#a0a09a",
};
function legendRow(active: boolean): CSSProperties {
  return {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "12px 14px",
    borderRadius: radius.md,
    border: `1px solid ${active ? colors.ink : colors.border}`,
    background: active ? colors.surfaceMuted : colors.surface,
    cursor: "pointer",
    transition: "all .15s",
  };
}
const mapKey: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 8,
  marginTop: 6,
  padding: 14,
  background: colors.surfaceMuted,
  borderRadius: radius.md,
  fontSize: 12,
  color: colors.textMuted,
};
const keyRow: CSSProperties = { display: "flex", alignItems: "center", gap: 10 };
const unservedCard: CSSProperties = {
  border: `1px dashed ${colors.ink}`,
  borderRadius: radius.xl,
  padding: "20px 24px",
  background: colors.surface,
};
const unservedRow: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 14,
  padding: "12px 0",
  borderTop: `1px solid ${colors.track}`,
};
const reasonChip: CSSProperties = {
  marginLeft: "auto",
  fontFamily: font.mono,
  fontSize: 11,
  padding: "3px 9px",
  border: `1px solid ${colors.ink}`,
  borderRadius: 7,
  textTransform: "capitalize",
};
const tableGrid: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 };
const tableCard: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.xl,
  padding: 22,
};
const driverBox: CSSProperties = { padding: 14, background: colors.surfaceMuted, borderRadius: radius.md };
const workerRow: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  padding: "12px 0",
  borderTop: `1px solid ${colors.track}`,
};
const workerBadge: CSSProperties = {
  width: 30,
  height: 30,
  borderRadius: 9,
  background: "#dedee2",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 11,
  fontWeight: 700,
  color: "#4a4a46",
};
