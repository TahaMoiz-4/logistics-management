/**
 * Objective-convergence line chart (SVG). Plots the "best so far" curve with a
 * shaded area and an optional lighter "current" trace, matching the prototype.
 *
 * Takes raw solver arrays; large traces (100k+ points) are downsampled to keep
 * the SVG light.
 */
import { useMemo } from "react";
import { font } from "@/theme/tokens";

interface Props {
  best: number[];
  current?: number[];
  width?: number;
  height?: number;
  /** dark = on the black live card; light = on white diagnostics card. */
  variant?: "dark" | "light";
  /** cap the number of plotted points (downsample). */
  maxPoints?: number;
}

export function ObjectiveChart({
  best,
  current,
  width = 520,
  height = 200,
  variant = "light",
  maxPoints = 240,
}: Props) {
  const { bestPts, curPts, gridLines, valLabels } = useMemo(
    () => build(best, current, width, height, maxPoints),
    [best, current, width, height, maxPoints],
  );

  const ink = variant === "dark" ? "#ffffff" : "#161616";
  const grid = variant === "dark" ? "rgba(255,255,255,.10)" : "#ededea";
  const gridText = variant === "dark" ? "#8a8a85" : "#a0a09a";
  // Keep the noisy "current" trace faint so it never competes with the best line.
  const curStroke = variant === "dark" ? "rgba(245,245,242,.18)" : "#dcdcd6";
  const areaFill = variant === "dark" ? "rgba(255,255,255,.10)" : "rgba(22,22,22,.05)";

  if (best.length === 0) {
    return null;
  }

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" style={{ display: "block" }}>
      {gridLines.map((gy, i) => (
        <g key={i}>
          <line x1={46} y1={gy} x2={width - 16} y2={gy} stroke={grid} strokeWidth={1} />
          <text
            x={40}
            y={gy + 3}
            textAnchor="end"
            fontSize={10}
            fontFamily={font.mono}
            fill={gridText}
          >
            {valLabels[i]}
          </text>
        </g>
      ))}

      {curPts && (
        <polyline points={curPts} fill="none" stroke={curStroke} strokeWidth={1} />
      )}

      {bestPts.area && <polygon points={bestPts.area} fill={areaFill} />}
      <polyline
        points={bestPts.line}
        fill="none"
        stroke={ink}
        strokeWidth={3.2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {bestPts.head && (
        <circle cx={bestPts.head[0]} cy={bestPts.head[1]} r={5} fill={ink} stroke={variant === "dark" ? "#161616" : "#fff"} strokeWidth={2.5} />
      )}
    </svg>
  );
}

function downsample(arr: number[], max: number): number[] {
  if (arr.length <= max) return arr;
  const step = arr.length / max;
  const out: number[] = [];
  for (let i = 0; i < max; i++) out.push(arr[Math.floor(i * step)]);
  out[out.length - 1] = arr[arr.length - 1]; // keep the final value exact
  return out;
}

function build(best: number[], current: number[] | undefined, W: number, H: number, maxPoints: number) {
  const b = downsample(best, maxPoints);
  const c = current ? downsample(current, maxPoints) : undefined;

  // Scale the y-axis to the BEST curve ONLY. The current trace is decorative
  // noise that can spike enormously (e.g. 5x best); if it drove the range, the
  // best line would collapse into a flat sliver at the bottom and its descent
  // (and the tracking dot's movement) would be invisible. So the range hugs
  // best, giving its improvement the full vertical space; current is drawn but
  // clamped into that view.
  const bLo = Math.min(...b);
  const bHi = Math.max(...b);
  let lo = bLo;
  let hi = bHi;
  // Lift the ceiling to include the current trace's *typical* level (a high
  // percentile, not its max) so the live dot moves within view instead of
  // pinning to the top on a rare spike.
  if (c && c.length) {
    hi = Math.max(hi, percentile(c, 0.9));
  }
  if (lo === hi) {
    // Perfectly flat: open a small symmetric band so the line sits mid-card.
    const eps = Math.max(Math.abs(hi) * 0.02, 1);
    lo -= eps;
    hi += eps;
  }
  const pad = (hi - lo) * 0.15;
  lo -= pad;
  hi += pad;
  const rng = hi - lo;

  // Wider left gutter so multi-digit axis labels aren't clipped.
  const LEFT = 46;
  const n = b.length;
  const px = (i: number) => LEFT + (i / Math.max(1, n - 1)) * (W - LEFT - 16);
  const clampY = (v: number) => Math.max(lo, Math.min(hi, v));
  const py = (v: number) => 18 + (1 - (clampY(v) - lo) / rng) * (H - 44);

  const line = b.map((v, i) => `${px(i)},${py(v)}`).join(" ");
  const area =
    n > 1 ? `${px(0)},${py(lo)} ${b.map((v, i) => `${px(i)},${py(v)}`).join(" ")} ${px(n - 1)},${py(lo)}` : "";
  // The tracking dot rides the CURRENT value (the live probe) when we have one,
  // so it visibly bobs up/down as the solver explores — even while best is flat.
  // Falls back to the best endpoint for static charts (diagnostics).
  const headVal = c && c.length ? c[c.length - 1] : b[n - 1];
  const head: [number, number] = [px(n - 1), py(headVal)];
  const curPts = c ? c.map((v, i) => `${px(i)},${py(v)}`).join(" ") : undefined;

  const gridLines: number[] = [];
  const valLabels: string[] = [];
  for (let g = 0; g <= 4; g++) {
    gridLines.push(18 + (g / 4) * (H - 44));
    valLabels.push(abbrev(hi - (g / 4) * rng));
  }

  return { bestPts: { line, area, head }, curPts, gridLines, valLabels };
}

/** Value at the p-th quantile (0..1) of an array, robust to spikes. */
function percentile(arr: number[], p: number): number {
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.round(p * (sorted.length - 1))));
  return sorted[idx];
}

/** Compact axis label: 633345 → "633k", 1462 → "1,462". */
function abbrev(v: number): string {
  const n = Math.round(v);
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (abs >= 10_000) return `${Math.round(n / 1000)}k`;
  return n.toLocaleString();
}
