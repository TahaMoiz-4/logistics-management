/**
 * Leaflet map for a solved plan: draws each driver route's real OSMnx road
 * polyline (GeoJSON MultiLineString, [lng,lat]) plus depot and order markers.
 *
 * Highlighting: passing highlightRouteId dims the other routes so a dispatcher
 * can isolate one driver's path (matches the legend "tap to isolate").
 */
import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Marker, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { MapDataOut } from "@/api/types";

/** Monochrome shades cycled across routes, matching the console aesthetic. */
const ROUTE_COLORS = ["#161616", "#3f6f52", "#6f6f6b", "#4a6b8a", "#8a5a4a", "#5c5c58"];

export function routeColor(index: number): string {
  return ROUTE_COLORS[index % ROUTE_COLORS.length];
}

/** Convert a GeoJSON MultiLineString ([lng,lat]) into Leaflet latlng arrays. */
function toLatLngs(coords: number[][][]): [number, number][][] {
  return coords.map((line) => line.map(([lng, lat]) => [lat, lng] as [number, number]));
}

const depotIcon = L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;background:#161616;border:2px solid #fff;border-radius:3px;transform:rotate(45deg);box-shadow:0 1px 4px rgba(0,0,0,.4)"></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

export function RouteMap({
  data,
  highlightRouteId,
  height = 460,
  orderFilter,
}: {
  data: MapDataOut;
  highlightRouteId?: number | null;
  height?: number;
  /**
   * When provided, only markers for these order IDs render. Works around a
   * backend quirk where /map-data can return markers for orders that aren't
   * part of this plan (deleted or belonging to other plans/dates).
   */
  orderFilter?: Set<number>;
}) {
  const center = useMemo<[number, number]>(() => [data.depot.lat, data.depot.lng], [data.depot]);
  const markers = orderFilter
    ? data.order_markers.filter((o) => orderFilter.has(o.order_id))
    : data.order_markers;

  return (
    <MapContainer
      center={center}
      zoom={12}
      style={{ height, width: "100%" }}
      scrollWheelZoom
      attributionControl={false}
    >
      <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />

      {/* road polylines per route */}
      {data.driver_routes.map((r, i) => {
        const dim = highlightRouteId != null && highlightRouteId !== r.driver_route_id;
        const color = routeColor(i);
        const paths = r.geometry
          ? toLatLngs(r.geometry.coordinates)
          : // fallback: straight lines through the ordered stop points
            [r.points.map((p) => [p.lat, p.lng] as [number, number])];
        return paths.map((path, j) => (
          <Polyline
            key={`${r.driver_route_id}-${j}`}
            positions={path}
            pathOptions={{
              color,
              weight: highlightRouteId === r.driver_route_id ? 5 : 3.5,
              opacity: dim ? 0.15 : 0.9,
            }}
          />
        ));
      })}

      {/* order markers */}
      {markers.map((o) => (
        <CircleMarker
          key={o.order_id}
          center={[o.lat, o.lng]}
          radius={6}
          pathOptions={
            o.served
              ? { color: "#161616", weight: 2, fillColor: "#ffffff", fillOpacity: 1 }
              : { color: "#b42318", weight: 2, dashArray: "3 3", fillColor: "#fff", fillOpacity: 1 }
          }
        >
          <Tooltip>
            ORD-{o.order_id} · {o.served ? "served" : "unserved"}
          </Tooltip>
        </CircleMarker>
      ))}

      {/* depot */}
      <Marker position={[data.depot.lat, data.depot.lng]} icon={depotIcon}>
        <Tooltip>Depot</Tooltip>
      </Marker>

      <FitBounds depot={data.depot} markers={markers} driverRoutes={data.driver_routes} />
    </MapContainer>
  );
}

/** Fit the map to the shown geometry when the dataset changes. */
function FitBounds({
  depot,
  markers,
  driverRoutes,
}: {
  depot: MapDataOut["depot"];
  markers: MapDataOut["order_markers"];
  driverRoutes: MapDataOut["driver_routes"];
}) {
  const map = useMap();
  useEffect(() => {
    const pts: [number, number][] = [[depot.lat, depot.lng]];
    markers.forEach((o) => pts.push([o.lat, o.lng]));
    driverRoutes.forEach((r) =>
      r.geometry?.coordinates.forEach((line) => line.forEach(([lng, lat]) => pts.push([lat, lng]))),
    );
    if (pts.length > 1) {
      map.fitBounds(L.latLngBounds(pts).pad(0.15));
    }
  }, [depot, markers, driverRoutes, map]);
  return null;
}
