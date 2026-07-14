/**
 * Login screen — split layout: editorial copy + form on the left, a dark
 * line-art panel on the right. Ported from the Nightingale prototype and wired
 * to the real POST /v1/auth/login via the auth context.
 */
import { useState, type CSSProperties, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { ApiError } from "@/api/client";
import { Spinner } from "@/components/Spinner";
import { colors, font, radius } from "@/theme/tokens";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("admin1");
  const [password, setPassword] = useState("password");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await login({ username: username.trim(), password });
      navigate("/", { replace: true });
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.status === 401 || err.status === 400
            ? "Invalid username or password."
            : err.message
          : "Something went wrong. Please try again.";
      setError(msg);
      setSubmitting(false);
    }
  }

  return (
    <div style={pageStyle}>
      {/* LEFT — copy + form */}
      <div style={leftStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 56 }}>
          <div style={logoMark}>N</div>
          <div style={{ fontWeight: 700, fontSize: 19, letterSpacing: "-.02em" }}>Nightingale</div>
        </div>

        <div style={eyebrow}>Dispatch Console</div>
        <h1 style={headline}>
          Route the day.
          <br />
          Watch it optimize.
        </h1>
        <p style={subcopy}>
          Plan, solve and dispatch field-service routes for your nursing fleet across Karachi.
        </p>

        <form style={{ maxWidth: 380, display: "flex", flexDirection: "column", gap: 14 }} onSubmit={onSubmit}>
          <label style={{ display: "block" }}>
            <span style={fieldLabel}>Username</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              style={inputStyle}
              onFocus={(e) => (e.currentTarget.style.borderColor = colors.ink)}
              onBlur={(e) => (e.currentTarget.style.borderColor = "#e0e0da")}
            />
          </label>
          <label style={{ display: "block" }}>
            <span style={fieldLabel}>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              style={inputStyle}
              onFocus={(e) => (e.currentTarget.style.borderColor = colors.ink)}
              onBlur={(e) => (e.currentTarget.style.borderColor = "#e0e0da")}
            />
          </label>

          {error && <div style={errorBox}>{error}</div>}

          <button type="submit" disabled={submitting} style={buttonStyle(submitting)}>
            {submitting && <Spinner size={17} color={colors.inkOnDark} track="rgba(245,245,242,.35)" />}
            <span>{submitting ? "Signing in…" : "Sign in"}</span>
          </button>

          <div style={demoHint}>demo · admin1 / password</div>
        </form>
      </div>

      {/* RIGHT — dark decorative panel */}
      <div style={rightStyle}>
        <div style={dotGrid} />
        <LoginArt />
      </div>
    </div>
  );
}

/**
 * Animated line-art ambulance speeding away, matching the monochrome console
 * aesthetic. Pure SVG (no external asset): the road dashes scroll, speed streaks
 * flicker, the body bobs, wheels spin, and the roof beacon pulses green.
 */
function LoginArt() {
  return (
    <svg
      width="460"
      height="320"
      viewBox="0 0 460 320"
      fill="none"
      style={{ position: "relative", zIndex: 1, maxWidth: "80%" }}
    >
      {/* road */}
      <line x1="0" y1="250" x2="460" y2="250" stroke="#3a3a36" strokeWidth="2.5" />
      {/* scrolling lane markings */}
      <line
        x1="0"
        y1="272"
        x2="460"
        y2="272"
        stroke="#4a4a45"
        strokeWidth="3"
        strokeDasharray="26 22"
        strokeLinecap="round"
        style={{ animation: "ng-road 0.6s linear infinite" }}
      />

      {/* speed streaks behind the vehicle */}
      <g stroke="#55554f" strokeWidth="2.5" strokeLinecap="round">
        <line x1="40" y1="150" x2="120" y2="150" style={{ animation: "ng-streak 0.7s linear infinite" }} />
        <line x1="20" y1="180" x2="90" y2="180" style={{ animation: "ng-streak 0.9s linear infinite 0.15s" }} />
        <line x1="50" y1="210" x2="130" y2="210" style={{ animation: "ng-streak 0.6s linear infinite 0.3s" }} />
      </g>

      {/* the ambulance — bobs subtly as it drives */}
      <g style={{ animation: "ng-drive 1.1s ease-in-out infinite", transformOrigin: "center" }}>
        {/* body */}
        <path
          d="M150 235 L150 175 Q150 168 158 168 L300 168 L336 200 L360 205 Q368 207 368 216 L368 235 Z"
          fill="#f5f5f2"
          stroke="none"
        />
        {/* cabin window */}
        <path d="M306 172 L332 197 L306 197 Z" fill="#161616" opacity="0.85" />
        {/* rear box window */}
        <rect x="168" y="182" width="34" height="26" rx="3" fill="#161616" opacity="0.14" />
        {/* red-cross emblem */}
        <g fill="#161616">
          <rect x="232" y="188" width="8" height="24" rx="1.5" />
          <rect x="224" y="196" width="24" height="8" rx="1.5" />
        </g>
        {/* roof beacon */}
        <rect
          x="196"
          y="158"
          width="18"
          height="10"
          rx="3"
          fill="#16a34a"
          style={{ animation: "ng-pulse 0.8s ease-in-out infinite" }}
        />
      </g>

      {/* wheels — sit on the road, spin in place */}
      <g>
        <g style={{ transformOrigin: "192px 236px", animation: "ng-spin 0.6s linear infinite" }}>
          <circle cx="192" cy="236" r="18" fill="#161616" stroke="#55554f" strokeWidth="3" />
          <circle cx="192" cy="236" r="6" fill="#55554f" />
          <line x1="192" y1="220" x2="192" y2="252" stroke="#2a2a27" strokeWidth="2" />
        </g>
        <g style={{ transformOrigin: "330px 236px", animation: "ng-spin 0.6s linear infinite" }}>
          <circle cx="330" cy="236" r="18" fill="#161616" stroke="#55554f" strokeWidth="3" />
          <circle cx="330" cy="236" r="6" fill="#55554f" />
          <line x1="330" y1="220" x2="330" y2="252" stroke="#2a2a27" strokeWidth="2" />
        </g>
      </g>
    </svg>
  );
}

// ---- styles ----
const pageStyle: CSSProperties = {
  minHeight: "100vh",
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  background: colors.bg,
};
const leftStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  justifyContent: "center",
  padding: "60px 8vw",
};
const logoMark: CSSProperties = {
  width: 36,
  height: 36,
  borderRadius: 10,
  background: colors.ink,
  color: colors.inkOnDark,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontWeight: 700,
  fontSize: 20,
};
const eyebrow: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 14,
  letterSpacing: ".1em",
  color: colors.textFaint,
  textTransform: "uppercase",
};
const headline: CSSProperties = {
  fontSize: 49,
  fontWeight: 700,
  letterSpacing: "-.035em",
  lineHeight: 1.02,
  margin: "14px 0 0",
};
const subcopy: CSSProperties = {
  fontSize: 17,
  color: colors.textMuted,
  margin: "18px 0 40px",
  maxWidth: 380,
  lineHeight: 1.55,
};
const fieldLabel: CSSProperties = {
  display: "block",
  fontSize: 14,
  fontWeight: 600,
  color: colors.textMuted,
  marginBottom: 7,
};
const inputStyle: CSSProperties = {
  width: "100%",
  height: 50,
  border: "1px solid #e0e0da",
  borderRadius: radius.lg,
  background: colors.surface,
  padding: "0 16px",
  fontSize: 17,
  outline: "none",
  transition: "border-color .18s",
};
const errorBox: CSSProperties = {
  fontSize: 15,
  color: "#b42318",
  background: "#fef3f2",
  border: "1px solid #fecdca",
  borderRadius: radius.md,
  padding: "10px 14px",
};
function buttonStyle(disabled: boolean): CSSProperties {
  return {
    height: 50,
    border: "none",
    borderRadius: radius.lg,
    background: colors.ink,
    color: colors.inkOnDark,
    fontSize: 17,
    fontWeight: 700,
    cursor: disabled ? "default" : "pointer",
    opacity: disabled ? 0.8 : 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    transition: "opacity .18s",
  };
}
const demoHint: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  color: colors.textFainter,
  textAlign: "center",
  marginTop: 4,
};
const rightStyle: CSSProperties = {
  background: colors.ink,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  position: "relative",
  overflow: "hidden",
};
const dotGrid: CSSProperties = {
  position: "absolute",
  inset: 0,
  backgroundImage: "radial-gradient(circle at 1px 1px, rgba(255,255,255,.06) 1px, transparent 0)",
  backgroundSize: "26px 26px",
};
