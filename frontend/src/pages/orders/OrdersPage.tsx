/**
 * Orders — the full order list with status filter chips and a "New order" form.
 * Data from GET /v1/orders; filtering is client-side over the fetched list.
 */
import { useMemo, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePageMeta } from "@/components/shell/pageMeta";
import { Icon } from "@/components/Icon";
import { Spinner } from "@/components/Spinner";
import { PriorityBadge, StatusBadge } from "@/components/Badge";
import { NewOrderForm } from "./NewOrderForm";
import { ordersApi } from "@/api/endpoints";
import type { Order } from "@/api/types";
import { shortDate, skillsSummary, timeWindow } from "@/lib/format";
import { colors, font, radius } from "@/theme/tokens";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "pending", label: "Pending" },
  { key: "assigned", label: "Assigned" },
  { key: "in_transit", label: "In transit" },
  { key: "delivered", label: "Delivered" },
  { key: "failed", label: "Failed" },
] as const;

const GRID = "1fr 1.3fr 1.2fr .8fr 1fr 1.4fr .8fr 1fr";

export function OrdersPage() {
  const [filter, setFilter] = useState<string>("all");
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["orders"],
    queryFn: () => ordersApi.list(),
  });

  usePageMeta("Orders", data ? `${data.length} orders` : "Service orders");

  const counts = useMemo(() => countByStatus(data ?? []), [data]);
  const rows = useMemo(
    () => (filter === "all" ? data ?? [] : (data ?? []).filter((o) => o.status === filter)),
    [data, filter],
  );

  return (
    <div className="ng-fade" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {/* filter chips + new-order */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        {FILTERS.map((f) => {
          const active = filter === f.key;
          const count = f.key === "all" ? data?.length ?? 0 : counts[f.key] ?? 0;
          return (
            <button key={f.key} onClick={() => setFilter(f.key)} style={chipStyle(active)}>
              <span>{f.label}</span>
              <span style={chipCount(active)}>{count}</span>
            </button>
          );
        })}
        <button style={addBtn} onClick={() => setFormOpen(true)}>
          <span style={{ display: "flex" }}>
            <Icon name="plus" size={17} />
          </span>
          New order
        </button>
      </div>

      {/* table */}
      <div style={tableCard}>
        <div style={{ ...tableRow, ...headRow }}>
          <span>Order</span>
          <span>Customer</span>
          <span>Location</span>
          <span>Date</span>
          <span>Window</span>
          <span>Skills</span>
          <span>Priority</span>
          <span>Status</span>
        </div>

        {isLoading && (
          <div style={stateBox}>
            <Spinner size={22} />
          </div>
        )}

        {isError && (
          <div style={stateBox}>
            <div style={{ textAlign: "center", color: colors.textMuted }}>
              <div style={{ marginBottom: 12 }}>{(error as Error)?.message ?? "Failed to load orders."}</div>
              <button style={retryBtn} onClick={() => refetch()}>
                Retry
              </button>
            </div>
          </div>
        )}

        {!isLoading && !isError && rows.length === 0 && (
          <div style={stateBox}>
            <div style={{ textAlign: "center", color: colors.textFaint }}>
              {filter === "all" ? "No orders yet. Create the first one." : `No ${filter.replace("_", " ")} orders.`}
            </div>
          </div>
        )}

        {rows.map((o) => (
          <OrderRow key={o.id} order={o} />
        ))}
      </div>

      <NewOrderForm open={formOpen} onClose={() => setFormOpen(false)} />
    </div>
  );
}

function OrderRow({ order }: { order: Order }) {
  const location = order.address_text || order.customer_name || "—";
  const skills = skillsSummary([...order.required_nurse_skills, ...order.required_tech_skills]);
  return (
    <div
      style={tableRow}
      onMouseEnter={(e) => (e.currentTarget.style.background = colors.surfaceMuted)}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      <span style={{ fontFamily: font.mono, fontSize: 14, fontWeight: 700 }}>ORD-{order.id}</span>
      <span style={{ fontWeight: 500 }}>{order.customer_name ?? `#${order.customer_id}`}</span>
      <span style={{ color: colors.textMuted }}>{location}</span>
      <span style={{ fontFamily: font.mono, fontSize: 14, color: colors.textMuted }}>
        {shortDate(order.service_date)}
      </span>
      <span style={{ fontFamily: font.mono, fontSize: 14, color: colors.textMuted }}>
        {timeWindow(order.timewindow_start, order.timewindow_end)}
      </span>
      <span style={{ color: colors.textMuted, fontSize: 14, textTransform: "capitalize" }}>{skills}</span>
      <span>
        <PriorityBadge priority={order.priority} />
      </span>
      <span>
        <StatusBadge status={order.status} />
      </span>
    </div>
  );
}

function countByStatus(orders: Order[]): Record<string, number> {
  const acc: Record<string, number> = {};
  for (const o of orders) acc[o.status] = (acc[o.status] ?? 0) + 1;
  return acc;
}

// ---- styles ----
function chipStyle(active: boolean): CSSProperties {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    height: 36,
    padding: "0 14px",
    borderRadius: radius.md,
    border: `1px solid ${active ? colors.ink : colors.border}`,
    background: active ? colors.ink : colors.surface,
    color: active ? colors.inkOnDark : colors.textMuted,
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
    transition: "all .15s",
  };
}
function chipCount(active: boolean): CSSProperties {
  return {
    fontFamily: font.mono,
    fontSize: 12,
    padding: "1px 7px",
    borderRadius: 20,
    background: active ? "rgba(255,255,255,.16)" : colors.track,
    color: active ? colors.inkOnDark : colors.textFaint,
  };
}
const addBtn: CSSProperties = {
  marginLeft: "auto",
  display: "inline-flex",
  alignItems: "center",
  gap: 8,
  height: 38,
  padding: "0 16px",
  borderRadius: radius.md,
  border: "none",
  background: colors.ink,
  color: colors.inkOnDark,
  fontSize: 15,
  fontWeight: 600,
  cursor: "pointer",
};
const tableCard: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.xl,
  overflow: "hidden",
};
const tableRow: CSSProperties = {
  display: "grid",
  gridTemplateColumns: GRID,
  gap: 14,
  alignItems: "center",
  padding: "15px 22px",
  borderTop: `1px solid ${colors.track}`,
  fontSize: 15,
  transition: "background .15s",
};
const headRow: CSSProperties = {
  background: colors.surfaceMuted,
  borderTop: "none",
  fontFamily: font.mono,
  fontSize: 11,
  letterSpacing: ".06em",
  textTransform: "uppercase",
  color: "#a0a09a",
};
const stateBox: CSSProperties = {
  padding: "48px 22px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  borderTop: `1px solid ${colors.track}`,
};
const retryBtn: CSSProperties = {
  height: 38,
  padding: "0 18px",
  border: "none",
  borderRadius: radius.md,
  background: colors.ink,
  color: colors.inkOnDark,
  fontWeight: 600,
  cursor: "pointer",
};
