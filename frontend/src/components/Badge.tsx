/**
 * Status + priority badges, ported from the prototype's statusBadge()/prioBadge().
 * Central so every screen labels statuses identically.
 */
import type { CSSProperties } from "react";
import { colors, font } from "@/theme/tokens";

const statusBase: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "3px 9px",
  borderRadius: 7,
  fontSize: 11,
  fontWeight: 600,
  whiteSpace: "nowrap",
};

const STATUS_STYLES: Record<string, CSSProperties> = {
  pending: { background: colors.track, color: "#8a8a85" },
  assigned: { background: "#e2e2dc", color: "#4a4a46" },
  in_transit: { background: colors.surface, border: `1px solid ${colors.ink}`, color: colors.ink },
  delivered: { background: colors.ink, color: colors.inkOnDark },
  failed: { background: colors.surface, border: `1px dashed ${colors.ink}`, color: colors.ink },
  draft: { background: colors.track, color: "#8a8a85" },
  optimizing: { background: colors.surface, border: `1px solid ${colors.ink}`, color: colors.ink },
  ready: { background: colors.ink, color: colors.inkOnDark },
  dispatched: { background: "#e2e2dc", color: "#4a4a46" },
  completed: { background: "#dcdce0", color: "#5c5c58" },
  active: { background: colors.ink, color: colors.inkOnDark },
  suspended: { background: colors.surface, border: `1px dashed ${colors.ink}`, color: colors.ink },
  inactive: { background: colors.track, color: "#8a8a85" },
};

const STATUS_LABELS: Record<string, string> = { in_transit: "In transit" };

function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.pending;
  const label = STATUS_LABELS[status] ?? titleCase(status);
  return <span style={{ ...statusBase, ...style }}>{label}</span>;
}

const prioBase: CSSProperties = {
  display: "inline-flex",
  padding: "2px 7px",
  borderRadius: 6,
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: ".03em",
  textTransform: "uppercase",
  fontFamily: font.mono,
};

const PRIO_STYLES: Record<string, CSSProperties> = {
  low: { background: colors.track, color: colors.textFaint },
  normal: { background: colors.track, color: colors.textMuted },
  high: { background: "#e2e2dc", color: "#2b2b2b" },
  urgent: { background: colors.ink, color: colors.inkOnDark },
};

export function PriorityBadge({ priority }: { priority: string }) {
  const style = PRIO_STYLES[priority] ?? PRIO_STYLES.normal;
  return <span style={{ ...prioBase, ...style }}>{priority}</span>;
}
