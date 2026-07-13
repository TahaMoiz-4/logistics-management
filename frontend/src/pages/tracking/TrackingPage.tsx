/**
 * Live Tracking — a Leaflet map of field staff (last-known GPS, polled every 3s)
 * with a selected-subject overlay card, a "tracked staff" list, and the
 * availability roster.
 *
 * Real positions are often sparse/stale, so empty and stale states are
 * first-class here.
 */
import { useMemo, useState, type CSSProperties } from "react";
import { usePageMeta } from "@/components/shell/pageMeta";
import { Icon } from "@/components/Icon";
import { Spinner } from "@/components/Spinner";
import { TrackingMap } from "@/components/map/TrackingMap";
import { useAvailabilityRoster, useLiveTracking } from "./useTracking";
import type { AvailabilityRosterEntry, LivePosition } from "@/api/types";
import { agoLabel } from "@/lib/format";
import { colors, font, radius } from "@/theme/tokens";

const TYPE_LABEL: Record<string, string> = {
  nurse: "Nurse",
  technician: "Technician",
  driver: "Driver",
  vehicle: "Vehicle",
};

export function TrackingPage() {
  const live = useLiveTracking();
  const roster = useAvailabilityRoster();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const positions = live.data?.positions ?? [];
  const freshCount = positions.filter((p) => !p.is_stale).length;

  usePageMeta("Live Tracking", positions.length ? `${positions.length} staff tracked` : "Field staff on the map");

  const selected = useMemo(
    () => positions.find((p) => p.subject_id === selectedId) ?? null,
    [positions, selectedId],
  );

  return (
    <div className="ng-fade" style={layout}>
      {/* map column */}
      <div style={mapCard}>
        {live.isLoading ? (
          <div style={mapState}>
            <Spinner size={24} />
          </div>
        ) : (
          <TrackingMap
            positions={positions}
            selectedId={selectedId}
            onSelect={setSelectedId}
            height={480}
          />
        )}

        {/* live badge */}
        <div style={liveBadge}>
          <span style={livePip} />
          {freshCount} live · polling 3s
        </div>

        {positions.length === 0 && !live.isLoading && (
          <div style={emptyOverlay}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>No positions reported</div>
            <div style={{ fontSize: 12, color: colors.textMuted }}>
              Field devices haven't sent GPS recently.
            </div>
          </div>
        )}

        {/* selected subject card */}
        {selected && (
          <div className="ng-fade" style={selCard}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15 }}>{selected.name ?? "Unknown"}</div>
                <div style={selMeta}>
                  {selected.employee_code ?? `#${selected.subject_id}`} ·{" "}
                  {TYPE_LABEL[selected.subject_type] ?? selected.subject_type}
                </div>
              </div>
              <button style={selClose} onClick={() => setSelectedId(null)} aria-label="Close">
                <Icon name="close" size={16} />
              </button>
            </div>
            <div style={selDivider} />
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12 }}>
              <div style={selRow}>
                <span style={{ color: "#8f8f8a" }}>Contact</span>
                <span style={{ fontFamily: font.mono }}>{selected.contact_number ?? "—"}</span>
              </div>
              <div style={selRow}>
                <span style={{ color: "#8f8f8a" }}>Last update</span>
                <span style={{ fontFamily: font.mono, color: selected.is_stale ? "#e0a37a" : colors.inkOnDark }}>
                  {agoLabel(selected.seconds_ago)}
                  {selected.is_stale && " · stale"}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* side column */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={sectionLabel}>Tracked staff</div>
        {positions.length === 0 && (
          <div style={{ fontSize: 12, color: colors.textFaint, padding: "4px 2px" }}>None reporting.</div>
        )}
        {positions.map((p) => (
          <TrackRow
            key={p.subject_id}
            pos={p}
            active={selectedId === p.subject_id}
            onClick={() => setSelectedId(p.subject_id)}
          />
        ))}

        <div style={{ ...sectionLabel, marginTop: 8 }}>Availability roster</div>
        {roster.isLoading && <Spinner size={18} />}
        {roster.data?.map((r) => (
          <RosterRow key={r.employee_id} entry={r} />
        ))}
      </div>
    </div>
  );
}

function TrackRow({
  pos,
  active,
  onClick,
}: {
  pos: LivePosition;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <div onClick={onClick} style={trackRow(active)}>
      <span style={mark(pos)} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 13 }}>{pos.name ?? "Unknown"}</div>
        <div style={{ fontFamily: font.mono, fontSize: 11, color: "#9a9a95" }}>
          {TYPE_LABEL[pos.subject_type] ?? pos.subject_type} · {pos.employee_code ?? `#${pos.subject_id}`}
        </div>
      </div>
      <span style={{ fontFamily: font.mono, fontSize: 10, color: pos.is_stale ? "#c98b6a" : "#b0b0aa", whiteSpace: "nowrap" }}>
        {agoLabel(pos.seconds_ago)}
      </span>
    </div>
  );
}

function RosterRow({ entry }: { entry: AvailabilityRosterEntry }) {
  return (
    <div style={rosterRow}>
      <span style={rosterDot(entry.available)} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 500, fontSize: 13 }}>{entry.name}</div>
        {entry.unavailable_reason && (
          <div style={{ fontSize: 11, color: "#a0a09a" }}>{entry.unavailable_reason}</div>
        )}
      </div>
      <span style={rosterStatus(entry.available)}>
        {entry.available ? "Available" : "Off"}
      </span>
    </div>
  );
}

function mark(pos: LivePosition): CSSProperties {
  const base: CSSProperties = { width: 12, height: 12, flexShrink: 0, opacity: pos.is_stale ? 0.4 : 1 };
  if (pos.subject_type === "driver") return { ...base, background: colors.ink, borderRadius: 3 };
  if (pos.subject_type === "vehicle")
    return { ...base, background: "#fff", border: `2px solid ${colors.ink}`, borderRadius: "50%" };
  return { ...base, background: colors.ink, borderRadius: "50%" };
}

// ---- styles ----
const layout: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 320px",
  gap: 20,
  alignItems: "start",
};
const mapCard: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.xl,
  overflow: "hidden",
  height: 480,
  position: "relative",
};
const mapState: CSSProperties = {
  height: "100%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};
const liveBadge: CSSProperties = {
  position: "absolute",
  top: 16,
  left: 16,
  zIndex: 1000,
  display: "flex",
  alignItems: "center",
  gap: 8,
  background: "rgba(255,255,255,.92)",
  backdropFilter: "blur(6px)",
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  padding: "8px 13px",
  fontFamily: font.mono,
  fontSize: 11,
};
const livePip: CSSProperties = {
  width: 7,
  height: 7,
  borderRadius: "50%",
  background: colors.accent,
  animation: "ng-pulse 1.6s infinite",
};
const emptyOverlay: CSSProperties = {
  position: "absolute",
  top: "50%",
  left: "50%",
  transform: "translate(-50%,-50%)",
  zIndex: 1000,
  background: "rgba(255,255,255,.94)",
  border: `1px solid ${colors.border}`,
  borderRadius: radius.lg,
  padding: "18px 22px",
  textAlign: "center",
  boxShadow: "0 8px 30px rgba(0,0,0,.08)",
};
const selCard: CSSProperties = {
  position: "absolute",
  bottom: 16,
  left: 16,
  zIndex: 1000,
  width: 260,
  background: colors.ink,
  color: colors.inkOnDark,
  borderRadius: radius.lg,
  padding: 18,
  boxShadow: "0 12px 40px rgba(0,0,0,.28)",
};
const selMeta: CSSProperties = { fontFamily: font.mono, fontSize: 11, color: "#8f8f8a", marginTop: 2 };
const selClose: CSSProperties = {
  background: "rgba(255,255,255,.1)",
  border: "none",
  color: colors.inkOnDark,
  width: 26,
  height: 26,
  borderRadius: 8,
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};
const selDivider: CSSProperties = { height: 1, background: "rgba(255,255,255,.1)", margin: "14px 0" };
const selRow: CSSProperties = { display: "flex", justifyContent: "space-between" };
const sectionLabel: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 10,
  letterSpacing: ".06em",
  textTransform: "uppercase",
  color: "#a0a09a",
};
function trackRow(active: boolean): CSSProperties {
  return {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "11px 14px",
    borderRadius: radius.md,
    border: `1px solid ${active ? colors.ink : colors.border}`,
    background: active ? colors.surfaceMuted : colors.surface,
    cursor: "pointer",
    transition: "all .15s",
  };
}
const rosterRow: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  padding: "11px 14px",
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
};
function rosterDot(available: boolean): CSSProperties {
  return {
    width: 9,
    height: 9,
    borderRadius: "50%",
    flexShrink: 0,
    background: available ? colors.accent : "#cfcfca",
  };
}
function rosterStatus(available: boolean): CSSProperties {
  return {
    fontSize: 11,
    fontWeight: 600,
    padding: "3px 9px",
    borderRadius: 7,
    background: available ? colors.ink : colors.track,
    color: available ? colors.inkOnDark : "#8a8a85",
  };
}
