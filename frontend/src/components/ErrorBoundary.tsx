/**
 * Catches render errors in the routed page tree so a single page crash shows a
 * readable message instead of a blank white screen. Resets when the route (via
 * `resetKey`) changes.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";
import { colors, font, radius } from "@/theme/tokens";

interface Props {
  children: ReactNode;
  resetKey?: string;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface to the console for debugging.
    console.error("Page crashed:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={box}>
          <div style={tag}>Something broke on this page</div>
          <div style={{ fontWeight: 700, fontSize: 18 }}>{this.state.error.name}</div>
          <div style={msg}>{this.state.error.message}</div>
          <pre style={stack}>{this.state.error.stack}</pre>
          <button style={btn} onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const box: React.CSSProperties = {
  border: `1px solid ${colors.border}`,
  background: colors.surface,
  borderRadius: radius.xl,
  padding: 28,
  display: "flex",
  flexDirection: "column",
  gap: 12,
  maxWidth: 800,
};
const tag: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  letterSpacing: ".06em",
  textTransform: "uppercase",
  color: "#b42318",
};
const msg: React.CSSProperties = { fontSize: 16, color: colors.text };
const stack: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  color: colors.textMuted,
  background: colors.surfaceMuted,
  padding: 14,
  borderRadius: radius.md,
  overflowX: "auto",
  maxHeight: 260,
  whiteSpace: "pre-wrap",
};
const btn: React.CSSProperties = {
  alignSelf: "flex-start",
  height: 38,
  padding: "0 18px",
  border: "none",
  borderRadius: radius.md,
  background: colors.ink,
  color: colors.inkOnDark,
  fontWeight: 600,
  cursor: "pointer",
};
