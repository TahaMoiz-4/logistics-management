/**
 * Fleet — tabbed read-only tables for Vehicles, Drivers and Depots.
 */
import { useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePageMeta } from "@/components/shell/pageMeta";
import { DataTable, type Column } from "@/components/DataTable";
import { StatusBadge } from "@/components/Badge";
import { depotsApi, driversApi, vehiclesApi } from "@/api/endpoints";
import type { Depot, Driver, Vehicle } from "@/api/types";
import { colors, font, radius } from "@/theme/tokens";

type Tab = "vehicles" | "drivers" | "depots";
const TABS: { key: Tab; label: string }[] = [
  { key: "vehicles", label: "Vehicles" },
  { key: "drivers", label: "Drivers" },
  { key: "depots", label: "Depots" },
];

export function FleetPage() {
  const [tab, setTab] = useState<Tab>("vehicles");
  usePageMeta("Fleet", "Vehicles, drivers & depots");

  return (
    <div className="ng-fade" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={tabBar}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} style={tabStyle(tab === t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "vehicles" && <VehiclesTable />}
      {tab === "drivers" && <DriversTable />}
      {tab === "depots" && <DepotsTable />}
    </div>
  );
}

function VehiclesTable() {
  const q = useQuery({ queryKey: ["vehicles"], queryFn: () => vehiclesApi.list() });
  const cols: Column<Vehicle>[] = [
    { key: "plate", header: "Plate", width: "1fr", render: (v) => <span style={mono}>{v.license_plate}</span> },
    { key: "type", header: "Type", width: ".8fr", render: (v) => <span style={cap}>{v.type}</span> },
    { key: "fuel", header: "Fuel", width: ".9fr", render: (v) => <span style={{ ...cap, color: colors.textMuted }}>{v.fuel_type ?? "—"}</span> },
    { key: "cap", header: "Capacity", width: ".9fr", render: (v) => <span style={{ color: colors.textMuted }}>{v.seating_capacity ?? "—"}</span> },
    { key: "depot", header: "Depot", width: "1.3fr", render: (v) => <span style={{ color: colors.textMuted }}>{v.depot_name ?? "—"}</span> },
    { key: "status", header: "Status", width: "1fr", render: (v) => <StatusBadge status={v.operational_status ?? "inactive"} /> },
  ];
  return (
    <DataTable
      columns={cols}
      rows={q.data}
      rowKey={(v) => v.id}
      isLoading={q.isLoading}
      isError={q.isError}
      errorMessage={(q.error as Error)?.message}
      onRetry={() => q.refetch()}
      emptyMessage="No vehicles registered."
    />
  );
}

function DriversTable() {
  const q = useQuery({ queryKey: ["drivers"], queryFn: () => driversApi.list() });
  const cols: Column<Driver>[] = [
    { key: "name", header: "Driver", width: "1.2fr", render: (d) => <span style={{ fontWeight: 600 }}>{d.name ?? `Driver #${d.id}`}</span> },
    { key: "vehicle", header: "Vehicle", width: ".9fr", render: (d) => <span style={{ ...mono, fontWeight: 700 }}>{d.vehicle_plate ?? "—"}</span> },
    { key: "skills", header: "Skills", width: "1.2fr", render: (d) => <span style={{ ...cap, color: colors.textMuted, fontSize: 12 }}>{d.skills.length ? d.skills.join(", ") : "—"}</span> },
    { key: "contact", header: "Contact", width: "1.1fr", render: (d) => <span style={{ ...mono, fontSize: 12, color: colors.textMuted }}>{d.contact_number ?? "—"}</span> },
    { key: "status", header: "Status", width: ".9fr", render: (d) => <StatusBadge status={d.operational_status ?? "active"} /> },
  ];
  return (
    <DataTable
      columns={cols}
      rows={q.data}
      rowKey={(d) => d.id}
      isLoading={q.isLoading}
      isError={q.isError}
      errorMessage={(q.error as Error)?.message}
      onRetry={() => q.refetch()}
      emptyMessage="No drivers registered."
    />
  );
}

function DepotsTable() {
  const q = useQuery({ queryKey: ["depots"], queryFn: () => depotsApi.list() });
  const cols: Column<Depot>[] = [
    { key: "name", header: "Depot", width: "1.2fr", render: (d) => <span style={{ fontWeight: 600 }}>{d.name}</span> },
    { key: "addr", header: "Address", width: "1.4fr", render: (d) => <span style={{ color: colors.textMuted }}>{d.address_text ?? "—"}</span> },
    {
      key: "coords",
      header: "Coordinates",
      width: "1fr",
      render: (d) => (
        <span style={{ ...mono, fontSize: 12, color: colors.textMuted }}>
          {d.lat != null && d.lng != null ? `${d.lat.toFixed(4)}, ${d.lng.toFixed(4)}` : "—"}
        </span>
      ),
    },
    { key: "status", header: "Status", width: ".8fr", render: (d) => <StatusBadge status={d.operational_status ?? "active"} /> },
  ];
  return (
    <DataTable
      columns={cols}
      rows={q.data}
      rowKey={(d) => d.id}
      isLoading={q.isLoading}
      isError={q.isError}
      errorMessage={(q.error as Error)?.message}
      onRetry={() => q.refetch()}
      emptyMessage="No depots registered."
    />
  );
}

// ---- styles ----
const tabBar: CSSProperties = {
  display: "inline-flex",
  gap: 4,
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.lg,
  padding: 4,
  alignSelf: "flex-start",
};
function tabStyle(active: boolean): CSSProperties {
  return {
    padding: "8px 18px",
    borderRadius: radius.md,
    border: "none",
    background: active ? colors.ink : "transparent",
    color: active ? colors.inkOnDark : colors.textMuted,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    transition: "all .15s",
  };
}
const mono: CSSProperties = { fontFamily: font.mono, fontSize: 12, fontWeight: 700 };
const cap: CSSProperties = { textTransform: "capitalize" };
