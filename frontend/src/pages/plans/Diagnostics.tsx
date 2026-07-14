/**
 * Solver diagnostics block: summary tiles, cost breakdown meters, the final
 * objective curve, and operator effectiveness bars — all from GET /diagnostics.
 */
import type { CSSProperties } from "react";
import { ObjectiveChart } from "@/components/ObjectiveChart";
import type { DiagnosticsOut } from "@/api/types";
import { humanizeSkill } from "@/lib/format";
import { colors, font, radius } from "@/theme/tokens";

export function Diagnostics({ diag }: { diag: DiagnosticsOut }) {
  const s = diag.summary;
  const tiles = [
    { label: "Iterations", value: s.iterations.toLocaleString() },
    { label: "Runtime", value: `${s.runtime_sec.toFixed(1)}s` },
    { label: "Iters/sec", value: Math.round(s.iters_per_sec).toLocaleString() },
    { label: "Improvement", value: `${s.improvement_pct.toFixed(1)}%` },
    { label: "Assigned", value: `${s.total_assigned}/${s.total_orders}` },
    { label: "Unserved", value: String(s.total_unserved) },
    { label: "Workers used", value: String(s.workers_used) },
    { label: "Best objective", value: Math.round(s.best_objective).toLocaleString() },
  ];

  const costs = Object.entries(diag.cost_breakdown)
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a);
  const costMax = Math.max(1, ...costs.map(([, v]) => v));

  const operators = flattenOperators(diag.operator_stats);
  const opMax = Math.max(1, ...operators.map((o) => o.used));

  return (
    <div style={card}>
      <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 4 }}>Solver diagnostics</div>
      <div style={{ fontSize: 14, color: colors.textFaint, marginBottom: 22 }}>
        What the ALNS solver optimized and how it got there.
      </div>

      {/* summary tiles */}
      <div style={tileGrid}>
        {tiles.map((t) => (
          <div key={t.label} style={tile}>
            <div style={tileLabel}>{t.label}</div>
            <div style={tileValue}>{t.value}</div>
          </div>
        ))}
      </div>

      <div style={twoCol}>
        {/* cost breakdown */}
        <div>
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 16 }}>Cost breakdown</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {costs.length === 0 && (
              <div style={{ fontSize: 14, color: colors.textFaint }}>No cost components.</div>
            )}
            {costs.map(([label, value]) => (
              <div key={label}>
                <div style={costRow}>
                  <span style={{ color: colors.textMuted, textTransform: "capitalize" }}>
                    {humanizeSkill(label)}
                  </span>
                  <span style={{ fontFamily: font.mono }}>{Math.round(value).toLocaleString()}</span>
                </div>
                <div style={track}>
                  <div style={{ ...bar, width: `${(value / costMax) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* objective curve + operators */}
        <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
          {diag.iteration_trace && diag.iteration_trace.best_so_far.length > 1 && (
            <div>
              <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 12 }}>Objective curve</div>
              <div style={{ border: `1px solid ${colors.track}`, borderRadius: radius.md, padding: 12 }}>
                <ObjectiveChart
                  best={diag.iteration_trace.best_so_far}
                  current={diag.iteration_trace.objectives}
                  height={170}
                />
              </div>
            </div>
          )}

          {operators.length > 0 && (
            <div>
              <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 14 }}>Operator effectiveness</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {operators.map((o) => (
                  <div key={o.kind + o.name} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={kindChip(o.kind)}>{o.kind}</span>
                      <span style={opName}>{humanizeSkill(o.name)}</span>
                      <span style={opCount}>
                        {o.used.toLocaleString()}× · ★{o.newBest}
                      </span>
                    </div>
                    <div style={{ height: 6, background: colors.track, borderRadius: 4, overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${(o.used / opMax) * 100}%`, background: colors.ink }} />
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ fontSize: 11, color: colors.textFaint, marginTop: 10, fontFamily: font.mono }}>
                bar = times used · ×N = runs · ★N = new-best hits
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface OpRow {
  kind: string;
  name: string;
  used: number;
  newBest: number;
}

/** operator_stats = { destroy: {op:{counts,total_used,...}}, repair: {...}, outcome_legend } */
function flattenOperators(stats: Record<string, unknown> | null): OpRow[] {
  if (!stats) return [];
  const legend = (stats.outcome_legend as string[] | undefined) ?? ["new_best", "better", "accepted", "rejected"];
  const newBestIdx = legend.indexOf("new_best");
  const out: OpRow[] = [];
  for (const kind of ["destroy", "repair"]) {
    const group = stats[kind] as Record<string, any> | undefined;
    if (!group) continue;
    for (const [name, v] of Object.entries(group)) {
      if (!v || typeof v !== "object") continue;
      const used = typeof v.total_used === "number" ? v.total_used : 0;
      const counts = Array.isArray(v.counts) ? v.counts : [];
      const newBest = newBestIdx >= 0 && counts[newBestIdx] != null ? counts[newBestIdx] : v.new_best ?? 0;
      out.push({ kind, name, used, newBest });
    }
  }
  return out.sort((a, b) => b.used - a.used).slice(0, 8);
}

// ---- styles ----
const card: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.xl,
  padding: 24,
};
const tileGrid: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(4, 1fr)",
  gap: 12,
  marginBottom: 26,
};
const tile: CSSProperties = { background: colors.surfaceMuted, borderRadius: radius.md, padding: 15 };
const tileLabel: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  letterSpacing: ".04em",
  textTransform: "uppercase",
  color: "#a0a09a",
};
const tileValue: CSSProperties = { fontFamily: font.mono, fontSize: 18, fontWeight: 700, marginTop: 6 };
const twoCol: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 };
const costRow: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  marginBottom: 5,
  fontSize: 14,
};
const track: CSSProperties = { height: 8, background: colors.track, borderRadius: 5, overflow: "hidden" };
const bar: CSSProperties = { height: "100%", background: colors.ink, borderRadius: 5 };
const opName: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  flex: 1,
  minWidth: 0,
  textTransform: "capitalize",
};
function kindChip(kind: string): CSSProperties {
  return {
    fontFamily: font.mono,
    fontSize: 10,
    padding: "2px 6px",
    borderRadius: 5,
    textTransform: "uppercase",
    background: kind === "destroy" ? "#efe6e4" : "#e4ece6",
    color: kind === "destroy" ? "#8a5a4a" : "#3f6f52",
  };
}
const opCount: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  color: colors.textMuted,
  flexShrink: 0,
  textAlign: "right",
  whiteSpace: "nowrap",
};
