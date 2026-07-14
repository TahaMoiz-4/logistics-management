/**
 * Authenticated app frame: fixed sidebar + a sticky header (page title/subtitle,
 * search affordance, live clock) wrapping the routed page via <Outlet>.
 *
 * Page title/subtitle come from route context set by each page through the
 * usePageMeta hook.
 */
import { useState, type CSSProperties, type ReactNode } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { useClock } from "./useClock";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Icon } from "@/components/Icon";
import { colors, font, radius } from "@/theme/tokens";
import { PageMetaContext, type PageMeta } from "./pageMeta";

export function AppShell() {
  const clock = useClock();
  const location = useLocation();
  const [meta, setMeta] = useState<PageMeta>({ title: "", subtitle: "" });

  return (
    <PageMetaContext.Provider value={setMeta}>
      <div style={rootStyle}>
        <Sidebar />
        <div style={mainColStyle}>
          <Header title={meta.title} subtitle={meta.subtitle} clock={clock} />
          <main style={mainStyle}>
            <ErrorBoundary resetKey={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </PageMetaContext.Provider>
  );
}

function Header({ title, subtitle, clock }: { title: string; subtitle: ReactNode; clock: string }) {
  return (
    <header style={headerStyle}>
      <div>
        <div style={{ fontSize: 21, fontWeight: 700, letterSpacing: "-.02em", lineHeight: 1 }}>
          {title}
        </div>
        <div style={{ fontSize: 14, color: colors.textFaint, marginTop: 3 }}>{subtitle}</div>
      </div>
      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
        <div style={searchStyle}>
          <span style={{ display: "flex" }}>
            <Icon name="search" size={17} />
          </span>
          <span>Search orders, workers…</span>
        </div>
        <div style={clockStyle}>
          <span style={livePip} />
          <span>{clock}</span>
        </div>
      </div>
    </header>
  );
}

// ---- styles ----
const rootStyle: CSSProperties = {
  display: "flex",
  minHeight: "100vh",
  maxWidth: 1600,
  margin: "0 auto",
  background: colors.bg,
};
const mainColStyle: CSSProperties = {
  flex: 1,
  minWidth: 0,
  display: "flex",
  flexDirection: "column",
  background: colors.bg,
};
const headerStyle: CSSProperties = {
  height: 66,
  flexShrink: 0,
  borderBottom: `1px solid ${colors.border}`,
  display: "flex",
  alignItems: "center",
  gap: 16,
  padding: "0 30px",
  background: colors.bg,
  position: "sticky",
  top: 0,
  zIndex: 20,
};
const mainStyle: CSSProperties = {
  flex: 1,
  overflowY: "auto",
  padding: 30,
};
const searchStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  height: 40,
  padding: "0 14px",
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  color: colors.textFaint,
  fontSize: 15,
  width: 230,
};
const clockStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  height: 40,
  padding: "0 14px",
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  fontFamily: font.mono,
  fontSize: 14,
};
const livePip: CSSProperties = {
  width: 7,
  height: 7,
  borderRadius: "50%",
  background: colors.accent,
  boxShadow: `0 0 0 3px ${colors.accentSoft}`,
  animation: "ng-pulse 2s infinite",
};
