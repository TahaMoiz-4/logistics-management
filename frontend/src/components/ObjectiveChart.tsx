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

  const ink = variant === "dark" ? "#f5f5f2" : "#161616";
  const grid = variant === "dark" ? "rgba(255,255,255,.08)" : "#ededea";
  const gridText = variant === "dark" ? "#6f6f6b" : "#b0b0aa";
  const curStroke = variant === "dark" ? "rgba(245,245,242,.35)" : "#c8c8c2";
  const areaFill = variant === "dark" ? "rgba(245,245,242,.08)" : "rgba(22,22,22,.05)";

  if (best.length === 0) {
    return null;
  }

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" style={{ display: "block" }}>
      {gridLines.map((gy, i) => (
        <g key={i}>
          <line x1={34} y1={gy} x2={width - 16} y2={gy} stroke={grid} strokeWidth={1} />
          <text
            x={28}
            y={gy + 3}
            textAnchor="end"
            fontSize={9}
            fontFamily={font.mono}
            fill={gridText}
          >
            {valLabels[i]}
          </text>
        </g>
      ))}

      {curPts && (
        <polyline points={curPts} fill="none" stroke={curStroke} strokeWidth={1.4} />
      )}

      {bestPts.area && <polygon points={bestPts.area} fill={areaFill} />}
      <polyline
        points={bestPts.line}
        fill="none"
        stroke={ink}
        strokeWidth={2.4}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {bestPts.head && (
        <circle cx={bestPts.head[0]} cy={bestPts.head[1]} r={4.5} fill={ink} stroke={variant === "dark" ? "#161616" : "#fff"} strokeWidth={2} />
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

  // Scale the y-axis primarily to the BEST curve so a flat/near-flat best line
  // stays readable. The (noisy) current trace can spike far above best; we let
  // it inform the top of the range only modestly, then clamp it into view so a
  // single spike doesn't flatten everything else against the axis.
  const bLo = Math.min(...b);
  const bHi = Math.max(...b);
  let lo = bLo;
  let hi = bHi;
  if (c && c.length) {
    const cHi = Math.max(...c);
    // allow the current trace to lift the ceiling, but only up to ~2.2x the
    // best-curve's own span above bHi — beyond that we clamp the drawn points.
    const bestSpan = Math.max(bHi - bLo, bHi * 0.01, 1);
    hi = Math.min(cHi, bHi + bestSpan * 2.2);
    lo = Math.min(lo, Math.min(...c));
  }
  if (lo === hi) {
    // Perfectly flat: open a small symmetric band so the line sits mid-card.
    const eps = Math.max(Math.abs(hi) * 0.01, 1);
    lo -= eps;
    hi += eps;
  }
  const pad = (hi - lo) * 0.12;
  lo -= pad;
  hi += pad;
  const rng = hi - lo;

  const n = b.length;
  const px = (i: number) => 34 + (i / Math.max(1, n - 1)) * (W - 50);
  const clampY = (v: number) => Math.max(lo, Math.min(hi, v));
  const py = (v: number) => 18 + (1 - (clampY(v) - lo) / rng) * (H - 44);

  const line = b.map((v, i) => `${px(i)},${py(v)}`).join(" ");
  const area =
    n > 1 ? `${px(0)},${py(lo)} ${b.map((v, i) => `${px(i)},${py(v)}`).join(" ")} ${px(n - 1)},${py(lo)}` : "";
  const head: [number, number] = [px(n - 1), py(b[n - 1])];
  const curPts = c ? c.map((v, i) => `${px(i)},${py(v)}`).join(" ") : undefined;

  const gridLines: number[] = [];
  const valLabels: string[] = [];
  for (let g = 0; g <= 4; g++) {
    gridLines.push(18 + (g / 4) * (H - 44));
    valLabels.push(String(Math.round(hi - (g / 4) * rng)));
  }

  return { bestPts: { line, area, head }, curPts, gridLines, valLabels };
}
