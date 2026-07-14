/**
 * Live solver view — connects to the real SSE stream and shows the objective
 * curve falling live, current stats, and a stage tracker. When the solve
 * finishes it reveals a button to the optimized result.
 *
 * If the user lands here on an already-finished plan (e.g. refresh), we detect
 * the terminal status and route straight to the result.
 */
import { useEffect, type CSSProperties } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { usePageMeta } from "@/components/shell/pageMeta";
import { Icon } from "@/components/Icon";
import { Spinner } from "@/components/Spinner";
import { ObjectiveChart } from "@/components/ObjectiveChart";
import { useSolverStream, type SolveStage } from "./useSolverStream";
import { usePlan } from "./usePlans";
import { colors, font, radius } from "@/theme/tokens";

const STAGES: { key: SolveStage; label: string }[] = [
  { key: "loading", label: "Loading road network & problem" },
  { key: "solving", label: "ALNS optimizing routes" },
  { key: "persisting", label: "Persisting solution" },
  { key: "done", label: "Done" },
];

export function PlanLivePage() {
  const { id } = useParams();
  const planId = Number(id);
  const navigate = useNavigate();
  const qc = useQueryClient();

  usePageMeta("Solving", `Plan PLN-${planId}`);

  // Fetch the plan once to know if it's already finished (refresh / deep-link).
  const { data: plan } = usePlan(planId, { refetchInterval: false });
  const alreadyDone = plan != null && plan.status !== "optimizing" && plan.status !== "draft";

  const solver = useSolverStream(planId, !alreadyDone);

  // On terminal states, refresh the plan caches so the result view is fresh.
  useEffect(() => {
    if (solver.stage === "done") {
      qc.invalidateQueries({ queryKey: ["route-plans"] });
    }
  }, [solver.stage, qc]);

  useEffect(() => {
    if (alreadyDone) navigate(`/plans/${planId}`, { replace: true });
  }, [alreadyDone, navigate, planId]);

  const stageIndex = STAGES.findIndex((s) => s.key === solver.stage);
  const done = solver.stage === "done";
  const errored = solver.stage === "error";

  return (
    <div className="ng-fade" style={layout}>
      {/* main solving card */}
      <div style={darkCard}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={livePip(errored)} />
          <span style={eyebrow}>
            ALNS solver · {errored ? "error" : done ? "complete" : "live stream"}
          </span>
        </div>
        <div style={{ fontSize: 32, fontWeight: 700, letterSpacing: "-.02em", marginTop: 20 }}>
          {errored ? "Solve failed" : done ? "Optimization complete" : "Objective converging"}
        </div>
        <div style={{ fontSize: 15, color: "#b7b7b2", marginTop: 4 }}>
          {errored
            ? solver.errorMessage ?? "The solver reported an error."
            : "Watch total cost fall as the solver explores thousands of route configurations."}
        </div>

        <div style={chartWrap}>
          {solver.bestTrace.length > 1 ? (
            <ObjectiveChart
              best={solver.bestTrace}
              current={solver.currentTrace}
              variant="dark"
              height={210}
            />
          ) : (
            <div style={chartPlaceholder}>
              <Spinner size={22} track="rgba(245,245,242,.2)" color="#f5f5f2" />
              <span style={{ fontFamily: font.mono, fontSize: 14, color: "#8f8f8a" }}>
                {solver.stage === "loading" ? "loading road network…" : "warming up…"}
              </span>
            </div>
          )}
        </div>

        <div style={statGrid}>
          <LiveStat label="Iteration" value={solver.iteration.toLocaleString()} />
          <LiveStat
            label="Best objective"
            value={solver.bestObjective != null ? Math.round(solver.bestObjective).toLocaleString() : "—"}
          />
          <LiveStat
            label="Current"
            value={solver.currentObjective != null ? Math.round(solver.currentObjective).toLocaleString() : "—"}
          />
          <LiveStat label="Elapsed" value={`${solver.elapsedSec.toFixed(1)}s`} />
        </div>
      </div>

      {/* side panel */}
      <div style={{ display: "flex", flexDirection: "column", gap: 18, position: "sticky", top: 20 }}>
        <div style={sideCard}>
          <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 18 }}>Solve progress</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {STAGES.map((s, i) => {
              const state: "done" | "active" | "pending" =
                done || i < stageIndex ? "done" : i === stageIndex ? "active" : "pending";
              return (
                <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span style={stageDot(state)}>
                    {state === "active" && !done && (
                      <span
                        style={{
                          width: 10,
                          height: 10,
                          border: "2px solid #e2e2dc",
                          borderTopColor: colors.ink,
                          borderRadius: "50%",
                          animation: "ng-spin .7s linear infinite",
                        }}
                      />
                    )}
                    {state === "done" && (
                      <span style={{ color: colors.inkOnDark, display: "flex" }}>
                        <Icon name="check" size={12} />
                      </span>
                    )}
                  </span>
                  <span style={stageLabel(state)}>{s.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        {done && (
          <button
            className="ng-fade"
            style={viewBtn}
            onClick={() => navigate(`/plans/${planId}`)}
            onMouseEnter={(e) => (e.currentTarget.style.transform = "translateY(-2px)")}
            onMouseLeave={(e) => (e.currentTarget.style.transform = "none")}
          >
            View optimized result
            <span style={{ display: "flex" }}>
              <Icon name="chevron" size={18} />
            </span>
          </button>
        )}
        {errored && (
          <button style={backBtn} onClick={() => navigate("/plans")}>
            Back to plans
          </button>
        )}
      </div>
    </div>
  );
}

function LiveStat({ label, value }: { label: string; value: string }) {
  return (
    <div style={liveStatBox}>
      <div style={liveStatLabel}>{label}</div>
      <div style={liveStatValue}>{value}</div>
    </div>
  );
}

// ---- styles ----
const layout: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 360px",
  gap: 20,
  alignItems: "start",
};
const darkCard: CSSProperties = {
  background: colors.ink,
  color: colors.inkOnDark,
  borderRadius: radius["2xl"],
  padding: 28,
  minHeight: 520,
  display: "flex",
  flexDirection: "column",
};
const eyebrow: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 14,
  letterSpacing: ".08em",
  textTransform: "uppercase",
  color: "#8f8f8a",
};
function livePip(errored: boolean): CSSProperties {
  return {
    width: 9,
    height: 9,
    borderRadius: "50%",
    background: errored ? "#e0736a" : colors.accent,
    boxShadow: `0 0 0 4px ${errored ? "rgba(224,115,106,.2)" : "rgba(22,163,74,.2)"}`,
    animation: "ng-pulse 1.4s infinite",
  };
}
const chartWrap: CSSProperties = {
  background: "#fff",
  borderRadius: radius.lg,
  padding: 16,
  marginTop: 22,
};
const chartPlaceholder: CSSProperties = {
  height: 210,
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  gap: 12,
};
const statGrid: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(4, 1fr)",
  gap: 12,
  marginTop: 22,
};
const liveStatBox: CSSProperties = {
  background: "rgba(255,255,255,.06)",
  borderRadius: radius.lg,
  padding: 15,
};
const liveStatLabel: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  letterSpacing: ".06em",
  textTransform: "uppercase",
  color: "#8f8f8a",
};
const liveStatValue: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 24,
  fontWeight: 700,
  marginTop: 6,
};
const sideCard: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.xl,
  padding: 22,
};
function stageDot(state: "done" | "active" | "pending"): CSSProperties {
  return {
    width: 26,
    height: 26,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    background: state === "done" ? colors.ink : state === "active" ? colors.surface : colors.track,
    border: state === "active" ? `1px solid ${colors.border}` : "none",
  };
}
function stageLabel(state: "done" | "active" | "pending"): CSSProperties {
  return {
    fontSize: 15,
    fontWeight: state === "pending" ? 400 : 600,
    color: state === "pending" ? colors.textFaint : colors.text,
  };
}
const viewBtn: CSSProperties = {
  height: 52,
  border: "none",
  borderRadius: radius.lg,
  background: colors.ink,
  color: colors.inkOnDark,
  fontSize: 17,
  fontWeight: 700,
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 10,
  transition: "transform .16s",
};
const backBtn: CSSProperties = {
  height: 46,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.lg,
  background: colors.surface,
  color: colors.text,
  fontSize: 16,
  fontWeight: 600,
  cursor: "pointer",
};
