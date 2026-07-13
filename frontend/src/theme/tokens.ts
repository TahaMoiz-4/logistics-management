/**
 * Nightingale design tokens.
 *
 * Ported from the Claude Design prototype, with two user-requested changes:
 *   1. Background moved from the "meh" warm off-white to a cooler light grey.
 *   2. Slightly larger display font sizes on the dashboard (applied per-component).
 *
 * Everything visual references these tokens so palette tweaks happen in one place.
 */
export const colors = {
  // Surfaces
  bg: "#f4f5f7", // app background (cool light grey — was #f3f3f0)
  bgSunken: "#eef0f3", // subtle sunken panels / rails
  surface: "#ffffff", // cards
  surfaceMuted: "#f7f8fa", // table header rows, inset chips (was #faf9f6)
  ink: "#161616", // near-black brand ink (buttons, hero cards)
  inkOnDark: "#f5f5f2", // text on dark surfaces

  border: "#e6e7eb", // hairline borders (was #e7e7e2)
  borderStrong: "#161616",
  track: "#eceef1", // progress-bar / meter track (was #f0f0ec)

  text: "#131313",
  textMuted: "#6f6f6b",
  textFaint: "#9a9a95",
  textFainter: "#b0b0aa",

  accent: "#16a34a", // green — live/success/link-hover
  accentSoft: "rgba(22,163,74,.16)",
} as const;

export const font = {
  sans: "'Space Grotesk', system-ui, -apple-system, sans-serif",
  mono: "'Space Mono', ui-monospace, monospace",
} as const;

export const radius = {
  sm: "8px",
  md: "11px",
  lg: "14px",
  xl: "18px",
  "2xl": "22px",
} as const;

/** Shared status→style maps, mirrored from the prototype's badge helpers. */
export const shadow = {
  card: "0 1px 2px rgba(16,17,20,.04)",
  lifted: "0 12px 40px rgba(0,0,0,.12)",
  accent: "0 6px 20px rgba(22,163,74,.28)",
} as const;
