/**
 * Right-side slide-over panel used for create/edit forms. Backdrop click and
 * Escape close it. Header (title + close) is fixed; body scrolls; an optional
 * footer holds actions.
 */
import { useEffect, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./Icon";
import { colors } from "@/theme/tokens";

export function SlideOver({
  open,
  title,
  subtitle,
  onClose,
  children,
  footer,
  width = 460,
}: {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  width?: number;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  // Portal to <body> so the backdrop-filter blurs the whole viewport — an
  // ancestor with its own filter/transform/overflow would otherwise neuter it.
  return createPortal(
    <div style={backdrop} onClick={onClose}>
      <div
        className="ng-slide"
        style={{ ...panel, width }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div style={header}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 17 }}>{title}</div>
            {subtitle && <div style={{ fontSize: 12, color: colors.textFaint, marginTop: 3 }}>{subtitle}</div>}
          </div>
          <button style={closeBtn} onClick={onClose} title="Close" aria-label="Close">
            <Icon name="close" size={18} />
          </button>
        </div>
        <div style={body}>{children}</div>
        {footer && <div style={footerStyle}>{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

const backdrop: CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(19,19,19,.34)",
  // Both properties: WebKit/Blink (Edge, Chrome, Safari) needs the -webkit- prefix.
  backdropFilter: "blur(5px)",
  WebkitBackdropFilter: "blur(5px)",
  zIndex: 90,
  display: "flex",
  justifyContent: "flex-end",
};
const panel: CSSProperties = {
  height: "100%",
  background: colors.bg,
  borderLeft: `1px solid ${colors.border}`,
  display: "flex",
  flexDirection: "column",
  boxShadow: "-20px 0 60px rgba(0,0,0,.12)",
};
const header: CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  padding: "22px 24px 18px",
  borderBottom: `1px solid ${colors.border}`,
};
const closeBtn: CSSProperties = {
  border: `1px solid ${colors.border}`,
  background: colors.surface,
  width: 34,
  height: 34,
  borderRadius: 9,
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: colors.textMuted,
};
const body: CSSProperties = {
  flex: 1,
  overflowY: "auto",
  padding: 24,
};
const footerStyle: CSSProperties = {
  padding: "16px 24px",
  borderTop: `1px solid ${colors.border}`,
  display: "flex",
  gap: 12,
  justifyContent: "flex-end",
  background: colors.bg,
};
