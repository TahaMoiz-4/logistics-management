/**
 * Left navigation rail: brand, nav items (with active state via router), and the
 * current-user footer with a logout button.
 */
import type { CSSProperties } from "react";
import { NavLink } from "react-router-dom";
import { Icon, type IconName } from "@/components/Icon";
import { useAuth } from "@/auth/AuthContext";
import { colors, font, radius } from "@/theme/tokens";

interface NavDef {
  to: string;
  label: string;
  icon: IconName;
  badge?: string;
}

const NAV: NavDef[] = [
  { to: "/", label: "Dashboard", icon: "dashboard" },
  { to: "/orders", label: "Orders", icon: "orders" },
  { to: "/plans", label: "Route Plans", icon: "plans" },
  { to: "/tracking", label: "Live Tracking", icon: "tracking" },
  { to: "/fleet", label: "Fleet", icon: "fleet" },
  { to: "/workers", label: "Workers", icon: "workers" },
];

export function Sidebar() {
  const { user, logout } = useAuth();
  const companyLabel = companyName(user?.company_id);
  const initials = (user?.username ?? "?").slice(0, 2).toUpperCase();

  return (
    <aside style={asideStyle}>
      <div style={{ padding: "26px 22px 20px", display: "flex", alignItems: "center", gap: 11 }}>
        <div style={brandMark}>N</div>
        <div style={{ lineHeight: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 16, letterSpacing: "-.02em" }}>Nightingale</div>
          <div style={brandSub}>DISPATCH CONSOLE</div>
        </div>
      </div>

      <nav style={{ padding: "8px 12px", display: "flex", flexDirection: "column", gap: 3, flex: 1 }}>
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            style={({ isActive }) => navItemStyle(isActive)}
          >
            <span style={{ display: "flex", width: 20, height: 20 }}>
              <Icon name={item.icon} />
            </span>
            <span>{item.label}</span>
            {item.badge && <span style={navBadge}>{item.badge}</span>}
          </NavLink>
        ))}
      </nav>

      <div style={{ padding: "14px 16px", borderTop: `1px solid ${colors.border}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
          <div style={avatar}>{initials}</div>
          <div style={{ lineHeight: 1.2, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{user?.username ?? "—"}</div>
            <div style={companyStyle}>{companyLabel}</div>
          </div>
          <button
            onClick={logout}
            title="Log out"
            style={logoutBtn}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = colors.ink;
              e.currentTarget.style.color = colors.text;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = colors.border;
              e.currentTarget.style.color = colors.textMuted;
            }}
          >
            <Icon name="logout" size={18} />
          </button>
        </div>
      </div>
    </aside>
  );
}

/** Placeholder company label until a /companies/me lookup is wired. */
function companyName(id: number | undefined): string {
  if (id === 1) return "Aga Khan Home Care";
  return id ? `Company #${id}` : "";
}

// ---- styles ----
const asideStyle: CSSProperties = {
  width: 244,
  flexShrink: 0,
  background: colors.bg,
  borderRight: `1px solid ${colors.border}`,
  display: "flex",
  flexDirection: "column",
  position: "sticky",
  top: 0,
  height: "100vh",
};
const brandMark: CSSProperties = {
  width: 34,
  height: 34,
  borderRadius: 10,
  background: colors.ink,
  color: colors.inkOnDark,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontWeight: 700,
  fontSize: 17,
};
const brandSub: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 10,
  color: colors.textFaint,
  marginTop: 3,
  letterSpacing: ".04em",
};
function navItemStyle(active: boolean): CSSProperties {
  return {
    display: "flex",
    alignItems: "center",
    gap: 11,
    padding: "9px 12px",
    borderRadius: radius.md,
    fontSize: 13.5,
    fontWeight: active ? 600 : 500,
    color: active ? colors.inkOnDark : colors.textMuted,
    background: active ? colors.ink : "transparent",
    transition: "background .16s, color .16s",
  };
}
const navBadge: CSSProperties = {
  marginLeft: "auto",
  fontFamily: font.mono,
  fontSize: 11,
  background: colors.ink,
  color: colors.inkOnDark,
  borderRadius: 20,
  padding: "1px 8px",
};
const avatar: CSSProperties = {
  width: 38,
  height: 38,
  borderRadius: 11,
  background: "#dedee2",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontWeight: 700,
  fontSize: 14,
  color: "#4a4a46",
};
const companyStyle: CSSProperties = {
  fontSize: 11,
  color: colors.textFaint,
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};
const logoutBtn: CSSProperties = {
  marginLeft: "auto",
  border: `1px solid ${colors.border}`,
  background: colors.surface,
  width: 32,
  height: 32,
  borderRadius: 9,
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: colors.textMuted,
  transition: "all .18s",
};
