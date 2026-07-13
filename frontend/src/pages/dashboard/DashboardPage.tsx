/**
 * Dashboard — today's operational snapshot from GET /v1/dashboard/today.
 *
 * Applies user design feedback: completion % sits inside the donut, display
 * numbers are larger, and the app uses the cooler background. Stat cards for
 * Orders and Workforce navigate to their sections; order/plan status breakdowns
 * render as labelled meters. Everything degrades gracefully to a zero state.
 */
import { useNavigate } from "react-router-dom";
import type { CSSProperties } from "react";
import { useDashboard } from "./useDashboard";
import { CompletionRing } from "./CompletionRing";
import { usePageMeta } from "@/components/shell/pageMeta";
import { Icon } from "@/components/Icon";
import { Spinner } from "@/components/Spinner";
import type { OrderStatusCounts, PlanStatusCounts } from "@/api/types";
import { colors, font, radius } from "@/theme/tokens";

export function DashboardPage() {
  const { data, isLoading, isError, error, refetch } = useDashboard();
  const navigate = useNavigate();
  usePageMeta("Dashboard", data ? `Operations for ${data.date}` : "Today's operations");

  if (isLoading) {
    return (
      <div style={centerBox}>
        <Spinner size={26} />
      </div>
    );
  }
  if (isError || !data) {
    return (
      <div style={centerBox}>
        <div style={{ textAlign: "center", color: colors.textMuted }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>Couldn't load the dashboard</div>
          <div style={{ fontSize: 13, marginBottom: 16 }}>
            {(error as Error | undefined)?.message ?? "Please try again."}
          </div>
          <button style={retryBtn} onClick={() => refetch()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const deliveredLabel = data.order_status_counts.delivered;

  return (
    <div className="ng-fade" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* top row: completion hero + two stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1.15fr 1fr 1fr", gap: 18 }}>
        <div style={heroCard}>
          <CompletionRing pct={data.completion_pct} />
          <div>
            <div style={heroEyebrow}>Today · Completion</div>
            <div style={heroBig}>
              {deliveredLabel}
              <span style={{ fontSize: 26, color: "#8f8f8a" }}>/{data.orders_today}</span>
            </div>
            <div style={{ fontSize: 13, color: "#b7b7b2", marginTop: 6, maxWidth: 200 }}>
              orders delivered so far today
            </div>
          </div>
        </div>

        <StatCard
          icon="orders"
          value={<span>{data.orders_today}</span>}
          caption="Orders scheduled today"
          onClick={() => navigate("/orders")}
          footer={<OrdersMiniBar counts={data.order_status_counts} />}
        />

        <StatCard
          icon="workers"
          value={
            <span>
              {data.workers_available}
              <span style={{ fontSize: 24, color: "#c2c2bc" }}>/{data.workers_total}</span>
            </span>
          }
          caption="Nurses available now"
          onClick={() => navigate("/workers")}
          footer={
            <div style={statFootMeta}>
              <span>{data.drivers_total} drivers</span>
              <span>·</span>
              <span>{data.vehicles_total} vehicles</span>
            </div>
          }
        />
      </div>

      {/* bottom row: order status breakdown + plans/quick-action */}
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 18 }}>
        <div style={panel}>
          <div style={panelHead}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>Order status</div>
            <div style={panelHint}>live · polling 10s</div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {orderStatusRows(data.order_status_counts).map(({ key, ...row }) => (
              <MeterRow key={key} {...row} />
            ))}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={panel}>
            <div style={panelHead}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Route plans today</div>
              <span style={{ fontFamily: font.mono, fontSize: 13, color: colors.textFaint }}>
                {data.plans_today}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {planStatusRows(data.plan_status_counts).map((row) => (
                <div key={row.key} style={planRow}>
                  <span style={{ fontSize: 13, color: colors.textMuted }}>{row.label}</span>
                  <span style={{ fontFamily: font.mono, fontSize: 13 }}>{row.count}</span>
                </div>
              ))}
              {data.plans_today === 0 && (
                <div style={{ fontSize: 12, color: colors.textFaint }}>No plans yet today.</div>
              )}
            </div>
          </div>

          <button
            onClick={() => navigate("/plans")}
            style={newPlanBtn}
            onMouseEnter={(e) => (e.currentTarget.style.transform = "translateY(-2px)")}
            onMouseLeave={(e) => (e.currentTarget.style.transform = "none")}
          >
            <span style={newPlanIcon}>
              <Icon name="plus" size={20} />
            </span>
            <span>
              <span style={{ display: "block", fontWeight: 700, fontSize: 15 }}>New route plan</span>
              <span style={{ display: "block", fontSize: 12, color: "#b7b7b2", marginTop: 2 }}>
                Pick orders → optimize with ALNS
              </span>
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------- stat card ----------
function StatCard({
  icon,
  value,
  caption,
  onClick,
  footer,
}: {
  icon: "orders" | "workers";
  value: React.ReactNode;
  caption: string;
  onClick: () => void;
  footer: React.ReactNode;
}) {
  return (
    <div
      onClick={onClick}
      style={statCard}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = colors.ink;
        e.currentTarget.style.transform = "translateY(-2px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = colors.border;
        e.currentTarget.style.transform = "none";
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ color: colors.textFaint }}>
          <Icon name={icon} />
        </span>
        <span style={{ fontFamily: font.mono, fontSize: 11, color: colors.textFaint }}>→</span>
      </div>
      <div style={statValue}>{value}</div>
      <div style={{ fontSize: 13, color: colors.textMuted, marginTop: 6 }}>{caption}</div>
      <div style={{ marginTop: 16 }}>{footer}</div>
    </div>
  );
}

/** Little segmented bar summarizing order statuses under the Orders stat. */
function OrdersMiniBar({ counts }: { counts: OrderStatusCounts }) {
  const segs = [
    { key: "delivered", v: counts.delivered, color: colors.ink },
    { key: "in_transit", v: counts.in_transit, color: "#6f6f6b" },
    { key: "assigned", v: counts.assigned, color: "#b6b6b0" },
    { key: "pending", v: counts.pending, color: "#d8d8d2" },
    { key: "failed", v: counts.failed, color: "#e4b7b2" },
  ];
  const total = segs.reduce((s, x) => s + x.v, 0);
  if (total === 0) {
    return <div style={{ height: 7, borderRadius: 6, background: colors.track }} />;
  }
  return (
    <div style={{ display: "flex", gap: 3, height: 7 }}>
      {segs
        .filter((s) => s.v > 0)
        .map((s) => (
          <div
            key={s.key}
            title={`${s.key}: ${s.v}`}
            style={{ flex: s.v, background: s.color, borderRadius: 6 }}
          />
        ))}
    </div>
  );
}

// ---------- meter rows ----------
interface MeterRowData {
  key: string;
  label: string;
  count: number;
  total: number;
  dot: string;
  bar: string;
}

function MeterRow({ label, count, total, dot, bar }: Omit<MeterRowData, "key">) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 7 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: dot }} />
          <span style={{ fontSize: 13, fontWeight: 500 }}>{label}</span>
        </div>
        <span style={{ fontFamily: font.mono, fontSize: 13 }}>{count}</span>
      </div>
      <div style={{ height: 7, background: colors.track, borderRadius: 6, overflow: "hidden" }}>
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background: bar,
            borderRadius: 6,
            transition: "width .5s cubic-bezier(.2,.7,.2,1)",
          }}
        />
      </div>
    </div>
  );
}

function orderStatusRows(c: OrderStatusCounts): MeterRowData[] {
  const total = c.pending + c.assigned + c.in_transit + c.delivered + c.failed;
  const defs: Array<[keyof OrderStatusCounts, string, string]> = [
    ["pending", "Pending", "#c9c9c3"],
    ["assigned", "Assigned", "#9a9a94"],
    ["in_transit", "In transit", "#5c5c58"],
    ["delivered", "Delivered", colors.ink],
    ["failed", "Failed", "#c98b84"],
  ];
  return defs.map(([key, label, color]) => ({
    key,
    label,
    count: c[key],
    total,
    dot: color,
    bar: color,
  }));
}

function planStatusRows(c: PlanStatusCounts) {
  const defs: Array<[keyof PlanStatusCounts, string]> = [
    ["draft", "Draft"],
    ["optimizing", "Optimizing"],
    ["ready", "Ready"],
    ["dispatched", "Dispatched"],
    ["completed", "Completed"],
    ["failed", "Failed"],
  ];
  return defs
    .map(([key, label]) => ({ key, label, count: c[key] }))
    .filter((r) => r.count > 0 || r.key === "ready" || r.key === "dispatched");
}

// ---- styles ----
const centerBox: CSSProperties = {
  minHeight: 300,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};
const retryBtn: CSSProperties = {
  height: 40,
  padding: "0 20px",
  border: "none",
  borderRadius: radius.md,
  background: colors.ink,
  color: colors.inkOnDark,
  fontWeight: 600,
  cursor: "pointer",
};
const heroCard: CSSProperties = {
  background: colors.ink,
  color: colors.inkOnDark,
  borderRadius: radius["2xl"],
  padding: 26,
  display: "flex",
  alignItems: "center",
  gap: 26,
  position: "relative",
  overflow: "hidden",
};
const heroEyebrow: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  letterSpacing: ".1em",
  color: "#8f8f8a",
  textTransform: "uppercase",
};
const heroBig: CSSProperties = {
  fontSize: 50,
  fontWeight: 700,
  letterSpacing: "-.03em",
  lineHeight: 1.05,
  marginTop: 6,
};
const statCard: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius["2xl"],
  padding: 24,
  cursor: "pointer",
  transition: "all .2s",
  display: "flex",
  flexDirection: "column",
};
const statValue: CSSProperties = {
  fontSize: 46,
  fontWeight: 700,
  letterSpacing: "-.03em",
  marginTop: 18,
  lineHeight: 1,
};
const statFootMeta: CSSProperties = {
  display: "flex",
  gap: 14,
  fontFamily: font.mono,
  fontSize: 11,
  color: colors.textFaint,
};
const panel: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius["2xl"],
  padding: 24,
};
const panelHead: CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  justifyContent: "space-between",
  marginBottom: 20,
};
const panelHint: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  color: colors.textFaint,
};
const planRow: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  fontSize: 13,
};
const newPlanBtn: CSSProperties = {
  background: colors.ink,
  color: colors.inkOnDark,
  border: "none",
  borderRadius: radius.xl,
  padding: 22,
  textAlign: "left",
  cursor: "pointer",
  transition: "transform .2s",
  display: "flex",
  alignItems: "center",
  gap: 14,
};
const newPlanIcon: CSSProperties = {
  width: 42,
  height: 42,
  borderRadius: 12,
  background: "rgba(255,255,255,.1)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};
