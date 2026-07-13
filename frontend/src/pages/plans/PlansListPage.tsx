/**
 * Route Plans list — every plan with status, objective and counts. Rows link to
 * the solved detail (or the live view if still optimizing). "New route plan"
 * starts the picker.
 */
import { useNavigate } from "react-router-dom";
import type { CSSProperties } from "react";
import { usePageMeta } from "@/components/shell/pageMeta";
import { Icon } from "@/components/Icon";
import { Spinner } from "@/components/Spinner";
import { StatusBadge } from "@/components/Badge";
import { usePlanList } from "./usePlans";
import type { RoutePlanSummary } from "@/api/types";
import { shortDate } from "@/lib/format";
import { colors, font, radius } from "@/theme/tokens";

const GRID = "1.8fr .8fr 1.1fr .6fr .6fr .8fr 1fr 28px";

export function PlansListPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = usePlanList();
  usePageMeta("Route Plans", data ? `${data.length} plans` : "Plan & optimize");

  const openPlan = (p: RoutePlanSummary) => {
    navigate(p.status === "optimizing" ? `/plans/${p.id}/live` : `/plans/${p.id}`);
  };

  return (
    <div className="ng-fade" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <button style={newBtn} onClick={() => navigate("/plans/new")}>
        <span style={{ display: "flex" }}>
          <Icon name="plus" size={18} />
        </span>
        New route plan
      </button>

      <div style={card}>
        <div style={{ ...row, ...head }}>
          <span>Plan</span>
          <span>Date</span>
          <span>Status</span>
          <span>Orders</span>
          <span>Routes</span>
          <span>Unserved</span>
          <span>Objective</span>
          <span />
        </div>

        {isLoading && (
          <div style={stateBox}>
            <Spinner size={22} />
          </div>
        )}
        {isError && (
          <div style={stateBox}>
            <div style={{ textAlign: "center", color: colors.textMuted }}>
              <div style={{ marginBottom: 12 }}>{(error as Error)?.message ?? "Failed to load plans."}</div>
              <button style={retryBtn} onClick={() => refetch()}>
                Retry
              </button>
            </div>
          </div>
        )}
        {!isLoading && !isError && data?.length === 0 && (
          <div style={stateBox}>
            <div style={{ color: colors.textFaint }}>No plans yet. Create the first route plan.</div>
          </div>
        )}

        {data?.map((p) => (
          <div
            key={p.id}
            style={{ ...row, cursor: "pointer" }}
            onClick={() => openPlan(p)}
            onMouseEnter={(e) => (e.currentTarget.style.background = colors.surfaceMuted)}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <span>
              <span style={{ fontWeight: 600, fontSize: 14, display: "block" }}>
                {p.name ?? `Plan ${p.id}`}
              </span>
              <span style={{ fontFamily: font.mono, fontSize: 11, color: "#a0a09a" }}>PLN-{p.id}</span>
            </span>
            <span style={monoMuted}>{shortDate(p.planned_date)}</span>
            <span>
              <StatusBadge status={p.status} />
            </span>
            <span style={mono}>{p.total_orders ?? "—"}</span>
            <span style={mono}>{p.total_routes ?? "—"}</span>
            <span style={mono}>{p.total_unserved ?? "—"}</span>
            <span style={{ ...mono, fontWeight: 700 }}>
              {p.objective_value != null ? Math.round(p.objective_value).toLocaleString() : "—"}
            </span>
            <span style={{ color: "#c2c2bc", display: "flex" }}>
              <Icon name="chevron" size={16} />
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

const newBtn: CSSProperties = {
  alignSelf: "flex-start",
  display: "inline-flex",
  alignItems: "center",
  gap: 10,
  height: 46,
  padding: "0 20px",
  borderRadius: radius.lg,
  border: "none",
  background: colors.ink,
  color: colors.inkOnDark,
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
};
const card: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.xl,
  overflow: "hidden",
};
const row: CSSProperties = {
  display: "grid",
  gridTemplateColumns: GRID,
  gap: 14,
  alignItems: "center",
  padding: "15px 22px",
  borderTop: `1px solid ${colors.track}`,
  fontSize: 13,
  transition: "background .15s",
};
const head: CSSProperties = {
  background: colors.surfaceMuted,
  borderTop: "none",
  fontFamily: font.mono,
  fontSize: 10,
  letterSpacing: ".06em",
  textTransform: "uppercase",
  color: "#a0a09a",
};
const mono: CSSProperties = { fontFamily: font.mono, fontSize: 13 };
const monoMuted: CSSProperties = { fontFamily: font.mono, fontSize: 12, color: colors.textMuted };
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
