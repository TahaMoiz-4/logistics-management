/**
 * Live tracking map (Leaflet). Plots each tracked subject's last-known GPS with
 * a shape by type (nurse=dot, driver=square, vehicle=ring). Stale subjects dim.
 * Clicking a marker selects it; the selected marker gets a pulsing ring.
 *
 * Positions update in place as the parent re-polls /tracking/live, so dots move
 * when the backend receives fresh GPS.
 */
import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Marker, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { LivePosition } from "@/api/types";

const KARACHI: [number, number] = [24.86, 67.01];

function markerHtml(pos: LivePosition, selected: boolean): string {
  const op = pos.is_stale ? 0.4 : 1;
  const ring = selected
    ? `<span style="position:absolute;inset:-8px;border:1.5px solid #161616;border-radius:50%;animation:ng-ping 1.6s ease-out infinite"></span>`
    : "";
  let shape: string;
  if (pos.subject_type === "driver") {
    shape = `<span style="width:15px;height:15px;background:#161616;border-radius:4px;opacity:${op};box-shadow:0 1px 4px rgba(0,0,0,.4)"></span>`;
  } else if (pos.subject_type === "vehicle") {
    shape = `<span style="width:15px;height:15px;background:#fff;border:2.5px solid #161616;border-radius:50%;opacity:${op}"></span>`;
  } else {
    // nurse / technician
    shape = `<span style="width:16px;height:16px;background:#161616;border-radius:50%;opacity:${op};display:flex;align-items:center;justify-content:center;box-shadow:0 1px 4px rgba(0,0,0,.4)"><span style="width:5px;height:5px;background:#f5f5f2;border-radius:50%"></span></span>`;
  }
  return `<div style="position:relative;display:flex;align-items:center;justify-content:center">${ring}${shape}</div>`;
}

export function TrackingMap({
  positions,
  selectedId,
  onSelect,
  height = 480,
}: {
  positions: LivePosition[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  height?: number;
}) {
  return (
    <MapContainer
      center={KARACHI}
      zoom={12}
      style={{ height, width: "100%" }}
      scrollWheelZoom
      attributionControl={false}
    >
      <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {positions.map((p) => (
        <SubjectMarker
          key={p.subject_id}
          pos={p}
          selected={selectedId === p.subject_id}
          onSelect={() => onSelect(p.subject_id)}
        />
      ))}
      <FitToPositions positions={positions} />
    </MapContainer>
  );
}

function SubjectMarker({
  pos,
  selected,
  onSelect,
}: {
  pos: LivePosition;
  selected: boolean;
  onSelect: () => void;
}) {
  // Rebuild the icon when selection/staleness changes.
  const icon = useMemo(
    () =>
      L.divIcon({
        className: "",
        html: markerHtml(pos, selected),
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      }),
    [pos, selected],
  );
  return (
    <Marker
      position={[pos.lat, pos.lng]}
      icon={icon}
      eventHandlers={{ click: onSelect }}
      // smooth glide when coordinates update between polls
      opacity={1}
    />
  );
}

/** Fit to the tracked subjects (or stay on Karachi when there are none). */
function FitToPositions({ positions }: { positions: LivePosition[] }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length === 0) return;
    if (positions.length === 1) {
      map.setView([positions[0].lat, positions[0].lng], 13);
      return;
    }
    const bounds = L.latLngBounds(positions.map((p) => [p.lat, p.lng] as [number, number]));
    map.fitBounds(bounds.pad(0.25));
    // only refit when the SET of subjects changes, not on every coord nudge
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positions.map((p) => p.subject_id).join(","), map]);
  return null;
}
