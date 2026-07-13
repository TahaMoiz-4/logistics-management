/**
 * Completion donut with the percentage rendered INSIDE the ring (per user
 * feedback), on the dark hero card. Larger type than the prototype.
 */
import { font } from "@/theme/tokens";

export function CompletionRing({ pct, size = 140 }: { pct: number; size?: number }) {
  const clamped = Math.max(0, Math.min(100, pct));
  const stroke = 12;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const dash = (clamped / 100) * c;

  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: "block" }}>
        {/* track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgba(255,255,255,.12)"
          strokeWidth={stroke}
        />
        {/* progress */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#f5f5f2"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dasharray .6s cubic-bezier(.2,.7,.2,1)" }}
        />
      </svg>
      {/* centered % label */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ fontSize: 34, fontWeight: 700, letterSpacing: "-.03em", lineHeight: 1 }}>
          {Math.round(clamped)}
          <span style={{ fontSize: 17, color: "#8f8f8a", fontFamily: font.mono }}>%</span>
        </span>
      </div>
    </div>
  );
}
