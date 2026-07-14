/**
 * Workers — a card grid of field staff (nurses/technicians) with skills, status,
 * shift and contact. Suspended workers surface their unavailable reason.
 */
import { useQuery } from "@tanstack/react-query";
import type { CSSProperties } from "react";
import { usePageMeta } from "@/components/shell/pageMeta";
import { Spinner } from "@/components/Spinner";
import { StatusBadge } from "@/components/Badge";
import { workersApi } from "@/api/endpoints";
import type { Worker } from "@/api/types";
import { humanizeSkill, initials } from "@/lib/format";
import { colors, font, radius } from "@/theme/tokens";

const TYPE_LABEL: Record<string, string> = { nurse: "Nurse", technician: "Technician" };

export function WorkersPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["workers"],
    queryFn: () => workersApi.list(),
  });
  usePageMeta("Workers", data ? `${data.length} field staff` : "Nursing staff");

  if (isLoading) {
    return (
      <div style={centerBox}>
        <Spinner size={24} />
      </div>
    );
  }
  if (isError) {
    return (
      <div style={centerBox}>
        <div style={{ textAlign: "center", color: colors.textMuted }}>
          <div style={{ marginBottom: 12 }}>{(error as Error)?.message ?? "Failed to load workers."}</div>
          <button style={retryBtn} onClick={() => refetch()}>
            Retry
          </button>
        </div>
      </div>
    );
  }
  if (!data || data.length === 0) {
    return (
      <div style={centerBox}>
        <div style={{ color: colors.textFaint }}>No workers registered.</div>
      </div>
    );
  }

  return (
    <div className="ng-fade" style={grid}>
      {data.map((w) => (
        <WorkerCard key={w.id} worker={w} />
      ))}
    </div>
  );
}

function WorkerCard({ worker }: { worker: Worker }) {
  const shift =
    worker.shift_start && worker.shift_end ? `${worker.shift_start}–${worker.shift_end}` : "—";
  return (
    <div
      style={card}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = colors.ink;
        e.currentTarget.style.transform = "translateY(-2px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = colors.border;
        e.currentTarget.style.transform = "none";
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
        <div style={avatar}>{initials(worker.name)}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 17 }}>{worker.name ?? `Worker #${worker.id}`}</div>
          <div style={{ fontFamily: font.mono, fontSize: 12, color: "#9a9a95", marginTop: 2 }}>
            {worker.employee_id ? `EMP-${worker.employee_id}` : `#${worker.id}`} ·{" "}
            {TYPE_LABEL[worker.worker_type] ?? worker.worker_type}
          </div>
        </div>
        <StatusBadge status={worker.operational_status ?? "active"} />
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 16 }}>
        {worker.skills.length === 0 && (
          <span style={{ fontSize: 14, color: colors.textFaint }}>No skills listed</span>
        )}
        {worker.skills.map((s) => (
          <span key={s} style={skillChip}>
            {humanizeSkill(s)}
          </span>
        ))}
      </div>

      <div style={footerRow}>
        <span>{shift}</span>
        <span>{worker.contact_number ?? "no contact"}</span>
      </div>

      {worker.unavailable_reason && <div style={reasonBox}>{worker.unavailable_reason}</div>}
    </div>
  );
}

// ---- styles ----
const grid: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
  gap: 16,
};
const centerBox: CSSProperties = { minHeight: 300, display: "flex", alignItems: "center", justifyContent: "center" };
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
const card: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.xl,
  padding: 22,
  transition: "all .2s",
};
const avatar: CSSProperties = {
  width: 46,
  height: 46,
  borderRadius: 13,
  background: colors.ink,
  color: colors.inkOnDark,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontWeight: 700,
  fontSize: 18,
  flexShrink: 0,
};
const skillChip: CSSProperties = {
  fontSize: 12,
  padding: "4px 10px",
  borderRadius: 8,
  background: colors.track,
  color: "#565652",
  textTransform: "capitalize",
};
const footerRow: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 16,
  marginTop: 16,
  paddingTop: 14,
  borderTop: `1px solid ${colors.track}`,
  fontFamily: font.mono,
  fontSize: 12,
  color: colors.textMuted,
};
const reasonBox: CSSProperties = {
  marginTop: 12,
  fontSize: 14,
  padding: "9px 12px",
  border: `1px dashed ${colors.ink}`,
  borderRadius: 10,
  color: colors.text,
};
