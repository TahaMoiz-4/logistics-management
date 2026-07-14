/**
 * Lightweight grid-based table shared by the list screens. Columns define a
 * header label, a CSS grid track width, and a cell renderer. Handles loading,
 * error (with retry), and empty states in a consistent card.
 */
import type { CSSProperties, ReactNode } from "react";
import { Spinner } from "./Spinner";
import { colors, font, radius } from "@/theme/tokens";

export interface Column<T> {
  key: string;
  header: string;
  /** CSS grid track (e.g. "1fr", ".8fr", "120px"). */
  width: string;
  render: (row: T) => ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  isLoading,
  isError,
  errorMessage,
  onRetry,
  emptyMessage = "Nothing here yet.",
}: {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string | number;
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string;
  onRetry?: () => void;
  emptyMessage?: string;
}) {
  const template = columns.map((c) => c.width).join(" ");

  return (
    <div style={card}>
      <div style={{ ...rowStyle(template), ...headStyle }}>
        {columns.map((c) => (
          <span key={c.key}>{c.header}</span>
        ))}
      </div>

      {isLoading && (
        <div style={stateBox}>
          <Spinner size={22} />
        </div>
      )}

      {isError && (
        <div style={stateBox}>
          <div style={{ textAlign: "center", color: colors.textMuted }}>
            <div style={{ marginBottom: 12 }}>{errorMessage ?? "Failed to load."}</div>
            {onRetry && (
              <button style={retryBtn} onClick={onRetry}>
                Retry
              </button>
            )}
          </div>
        </div>
      )}

      {!isLoading && !isError && rows?.length === 0 && (
        <div style={stateBox}>
          <div style={{ color: colors.textFaint }}>{emptyMessage}</div>
        </div>
      )}

      {!isLoading &&
        !isError &&
        rows?.map((row) => (
          <div
            key={rowKey(row)}
            style={rowStyle(template)}
            onMouseEnter={(e) => (e.currentTarget.style.background = colors.surfaceMuted)}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            {columns.map((c) => (
              <span key={c.key} style={cellStyle}>
                {c.render(row)}
              </span>
            ))}
          </div>
        ))}
    </div>
  );
}

const card: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.xl,
  overflow: "hidden",
};
function rowStyle(template: string): CSSProperties {
  return {
    display: "grid",
    gridTemplateColumns: template,
    gap: 14,
    alignItems: "center",
    padding: "16px 22px",
    borderTop: `1px solid ${colors.track}`,
    fontSize: 15,
    transition: "background .15s",
  };
}
const headStyle: CSSProperties = {
  background: colors.surfaceMuted,
  borderTop: "none",
  fontFamily: font.mono,
  fontSize: 11,
  letterSpacing: ".06em",
  textTransform: "uppercase",
  color: "#a0a09a",
};
const cellStyle: CSSProperties = { minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" };
const stateBox: CSSProperties = {
  padding: "48px 22px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  borderTop: `1px solid ${colors.track}`,
};
const retryBtn: CSSProperties = {
  height: 38,
  padding: "0 18px",
  border: "none",
  borderRadius: radius.md,
  background: colors.ink,
  color: colors.inkOnDark,
  fontWeight: 600,
  cursor: "pointer",
};
