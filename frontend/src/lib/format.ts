/** Shared display formatters, kept tiny and dependency-free. */

/** "iv_administration" -> "iv administration" */
export function humanizeSkill(skill: string): string {
  return skill.replace(/_/g, " ");
}

/** Join skills for a compact table cell, or a dash when empty. */
export function skillsSummary(skills: string[]): string {
  if (!skills.length) return "—";
  return skills.map(humanizeSkill).join(", ");
}

/** Render a HH:MM–HH:MM window, trimming seconds; dash when open-ended. */
export function timeWindow(start: string | null, end: string | null): string {
  const s = trimTime(start);
  const e = trimTime(end);
  if (!s && !e) return "—";
  return `${s || "…"}–${e || "…"}`;
}

function trimTime(t: string | null): string {
  if (!t) return "";
  // Accepts "09:00", "09:00:00", or an ISO time; keep HH:MM.
  const m = t.match(/(\d{1,2}):(\d{2})/);
  return m ? `${m[1].padStart(2, "0")}:${m[2]}` : t;
}

/** Two-letter initials from a name/username. */
export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Compact relative age from a seconds count: "22s", "6m", "2h", "3d". */
export function agoLabel(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  const m = seconds / 60;
  if (m < 60) return `${Math.round(m)}m ago`;
  const h = m / 60;
  if (h < 24) return `${Math.round(h)}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

/** A short date like "20 Jul" from an ISO date string. */
export function shortDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}
