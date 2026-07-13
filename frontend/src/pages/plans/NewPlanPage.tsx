/**
 * New route plan — pick servable orders and launch the solver.
 *
 * Backend rule: one plan optimizes exactly ONE date. Orders are grouped by
 * service_date; selecting across dates is blocked with a clear nudge. On solve
 * we POST /route-plans and jump to the live solver view.
 */
import { useMemo, useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { usePageMeta } from "@/components/shell/pageMeta";
import { Icon } from "@/components/Icon";
import { Spinner } from "@/components/Spinner";
import { PriorityBadge } from "@/components/Badge";
import { useServableOrders } from "./usePlans";
import { routePlansApi } from "@/api/endpoints";
import { useToast } from "@/components/Toast";
import { ApiError } from "@/api/client";
import type { ServableOrder } from "@/api/types";
import { shortDate, skillsSummary, timeWindow } from "@/lib/format";
import { colors, font, radius } from "@/theme/tokens";

const REPAIR_MODE = "shuttle_aware";
const MAX_RUNTIME_LABEL = "30 s";

export function NewPlanPage() {
  const navigate = useNavigate();
  const toast = useToast();
  usePageMeta("New route plan", "Pick orders → optimize with ALNS");

  const { data: orders, isLoading, isError, error, refetch } = useServableOrders();
  const [picked, setPicked] = useState<Set<number>>(new Set());

  const groups = useMemo(() => groupByDate(orders ?? []), [orders]);
  const pickedOrders = useMemo(
    () => (orders ?? []).filter((o) => picked.has(o.id)),
    [orders, picked],
  );
  const pickedDates = useMemo(
    () => new Set(pickedOrders.map((o) => o.service_date)),
    [pickedOrders],
  );
  const multiDate = pickedDates.size > 1;

  const toggle = (id: number) =>
    setPicked((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const create = useMutation({
    mutationFn: () => {
      const date = pickedOrders[0]?.service_date ?? null;
      return routePlansApi.create({
        order_ids: [...picked],
        planned_date: date,
        repair_mode: REPAIR_MODE,
        name: date ? `${shortDate(date)} · plan` : "Route plan",
      });
    },
    onSuccess: (res) => {
      navigate(`/plans/${res.route_plan_id}/live`);
    },
    onError: (err) => {
      toast.show(err instanceof ApiError ? err.message : "Could not start the solve.");
    },
  });

  const canSolve = picked.size > 0 && !multiDate && !create.isPending;

  return (
    <div className="ng-fade" style={layout}>
      {/* left: pick list */}
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={infoBar}>
          Pick servable orders from <strong>one date</strong> — the solver optimizes one day per plan.
        </div>

        {isLoading && (
          <div style={centerBox}>
            <Spinner size={22} />
          </div>
        )}
        {isError && (
          <div style={centerBox}>
            <div style={{ textAlign: "center", color: colors.textMuted }}>
              <div style={{ marginBottom: 12 }}>{(error as Error)?.message ?? "Failed to load orders."}</div>
              <button style={smallDark} onClick={() => refetch()}>
                Retry
              </button>
            </div>
          </div>
        )}
        {!isLoading && !isError && groups.length === 0 && (
          <div style={centerBox}>
            <div style={{ color: colors.textFaint }}>
              No servable orders. Orders need a location and a future service date.
            </div>
          </div>
        )}

        {groups.map((g) => (
          <div key={g.date}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 12 }}>
              <span style={{ fontWeight: 700, fontSize: 15 }}>{shortDate(g.date)}</span>
              <span style={{ fontFamily: font.mono, fontSize: 12, color: "#a0a09a" }}>
                {g.orders.length} orders
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {g.orders.map((o) => (
                <PickRow key={o.id} order={o} checked={picked.has(o.id)} onToggle={() => toggle(o.id)} />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* right: solve setup */}
      <div style={setupCard}>
        <div style={{ fontWeight: 700, fontSize: 16 }}>Solve setup</div>
        <div style={selectedBox}>
          <span style={{ fontSize: 13, color: colors.textMuted }}>Orders selected</span>
          <span style={{ fontFamily: font.mono, fontSize: 26, fontWeight: 700 }}>{picked.size}</span>
        </div>

        {multiDate && (
          <div style={warnBox}>
            Orders span multiple dates. One plan = one day — deselect the extras.
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 13 }}>
          <div style={kv}>
            <span style={{ color: colors.textMuted }}>Repair mode</span>
            <span style={{ fontFamily: font.mono }}>{REPAIR_MODE}</span>
          </div>
          <div style={kv}>
            <span style={{ color: colors.textMuted }}>Max runtime</span>
            <span style={{ fontFamily: font.mono }}>{MAX_RUNTIME_LABEL}</span>
          </div>
        </div>

        <button style={optimizeBtn(canSolve)} disabled={!canSolve} onClick={() => create.mutate()}>
          {create.isPending ? (
            <Spinner size={16} color={colors.inkOnDark} track="rgba(245,245,242,.35)" />
          ) : (
            <span style={{ display: "flex" }}>
              <Icon name="bolt" size={18} />
            </span>
          )}
          {create.isPending ? "Starting…" : "Optimize"}
        </button>
        {picked.size > 0 && (
          <button style={clearBtn} onClick={() => setPicked(new Set())} disabled={create.isPending}>
            Clear selection
          </button>
        )}
      </div>
    </div>
  );
}

function PickRow({
  order,
  checked,
  onToggle,
}: {
  order: ServableOrder;
  checked: boolean;
  onToggle: () => void;
}) {
  const skills = skillsSummary(order.required_skills ?? []);
  return (
    <div onClick={onToggle} style={pickRow(checked)}>
      <span style={checkbox(checked)}>{checked && <Icon name="check" size={13} />}</span>
      <span style={{ fontFamily: font.mono, fontSize: 12, fontWeight: 700, width: 74 }}>
        ORD-{order.id}
      </span>
      <span style={{ fontWeight: 500, fontSize: 13, width: 130, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {order.name ?? `ORD-${order.id}`}
      </span>
      <span style={{ color: colors.textMuted, fontSize: 13, flex: 1, minWidth: 0 }}>
        {order.address_text ?? "—"}
      </span>
      <span style={{ fontFamily: font.mono, fontSize: 12, color: colors.textMuted }}>
        {timeWindow(order.timewindow_start, order.timewindow_end)}
      </span>
      <span style={{ color: "#9a9a95", fontSize: 12, width: 120, textTransform: "capitalize", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {skills}
      </span>
      <PriorityBadge priority={order.priority} />
    </div>
  );
}

function groupByDate(orders: ServableOrder[]): { date: string; orders: ServableOrder[] }[] {
  const map = new Map<string, ServableOrder[]>();
  for (const o of orders) {
    const key = o.service_date ?? "—";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(o);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, os]) => ({ date, orders: os }));
}

// ---- styles ----
const layout: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 320px",
  gap: 20,
  alignItems: "start",
};
const infoBar: CSSProperties = {
  fontSize: 13,
  color: colors.textMuted,
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.lg,
  padding: "14px 18px",
};
const centerBox: CSSProperties = {
  minHeight: 180,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};
function pickRow(checked: boolean): CSSProperties {
  return {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "12px 14px",
    borderRadius: radius.md,
    border: `1px solid ${checked ? colors.ink : colors.border}`,
    background: checked ? colors.surfaceMuted : colors.surface,
    cursor: "pointer",
    transition: "all .15s",
  };
}
function checkbox(checked: boolean): CSSProperties {
  return {
    width: 20,
    height: 20,
    borderRadius: 6,
    border: `1.5px solid ${checked ? colors.ink : "#cfcfca"}`,
    background: checked ? colors.ink : colors.surface,
    color: colors.inkOnDark,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  };
}
const setupCard: CSSProperties = {
  position: "sticky",
  top: 20,
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.xl,
  padding: 22,
  display: "flex",
  flexDirection: "column",
  gap: 16,
};
const selectedBox: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "14px 16px",
  background: colors.surfaceMuted,
  borderRadius: radius.md,
};
const warnBox: CSSProperties = {
  fontSize: 12,
  padding: "11px 14px",
  border: `1px dashed ${colors.ink}`,
  borderRadius: radius.md,
  color: colors.text,
  fontWeight: 500,
};
const kv: CSSProperties = { display: "flex", justifyContent: "space-between" };
function optimizeBtn(enabled: boolean): CSSProperties {
  return {
    height: 50,
    border: "none",
    borderRadius: radius.lg,
    background: colors.ink,
    color: colors.inkOnDark,
    fontSize: 15,
    fontWeight: 700,
    cursor: enabled ? "pointer" : "default",
    opacity: enabled ? 1 : 0.4,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
  };
}
const clearBtn: CSSProperties = {
  background: "none",
  border: "none",
  color: "#a0a09a",
  fontSize: 12,
  cursor: "pointer",
};
const smallDark: CSSProperties = {
  height: 36,
  padding: "0 16px",
  border: "none",
  borderRadius: radius.md,
  background: colors.ink,
  color: colors.inkOnDark,
  fontWeight: 600,
  cursor: "pointer",
};
