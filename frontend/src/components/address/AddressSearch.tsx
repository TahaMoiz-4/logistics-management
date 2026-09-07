/**
 * Address autocomplete for order/customer/depot forms.
 *
 * Replaces hand-entered lat/lng decimals: the dispatcher types an address, picks
 * a suggestion, and the form receives coordinates plus a human-readable
 * address_text. Manual coordinate entry stays available in the parent form as a
 * fallback, because informal Karachi addresses ("third house past the blue
 * gate") are not in OpenStreetMap.
 *
 * Results outside the routable road network are shown greyed out with an
 * explanation rather than hidden — a dispatcher may know a place OSM does not,
 * and silently dropping a result the user can see on a map is confusing. They
 * are not selectable, since the solver cannot route to them.
 */
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Spinner } from "@/components/Spinner";
import { colors, font, radius, shadow } from "@/theme/tokens";
import type { GeocodeResult } from "@/api/types";
import { useAddressSearch } from "./useAddressSearch";

export interface SelectedAddress {
  lat: number;
  lng: number;
  address_text: string;
}

export function AddressSearch({
  value,
  onSelect,
  onClear,
  placeholder = "Search an address, area or landmark…",
}: {
  /** The currently chosen address, if any. */
  value: SelectedAddress | null;
  onSelect: (address: SelectedAddress) => void;
  onClear: () => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const { results, isSearching, failed } = useAddressSearch(query);

  // Reset the keyboard cursor whenever the result set changes underneath it.
  useEffect(() => setActiveIndex(0), [results]);

  // Close the dropdown on an outside click — the input itself keeps focus
  // handling, so this only needs to catch clicks elsewhere on the page.
  useEffect(() => {
    if (!open) return;
    function onDocumentClick(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocumentClick);
    return () => document.removeEventListener("mousedown", onDocumentClick);
  }, [open]);

  function choose(result: GeocodeResult) {
    if (result.routable === false) return; // not selectable — see file header
    onSelect({ lat: result.lat, lng: result.lng, address_text: result.address_text });
    setQuery("");
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (i - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      // The form would otherwise submit while the dispatcher is still picking.
      e.preventDefault();
      choose(results[activeIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  // A chosen address replaces the search box entirely, so the form always shows
  // what will actually be saved rather than the text used to find it.
  if (value) {
    return (
      <div style={chosenBox}>
        <div style={{ minWidth: 0 }}>
          <div style={chosenLabel}>{value.address_text}</div>
          <div style={chosenCoords}>
            {value.lat.toFixed(5)}, {value.lng.toFixed(5)}
          </div>
        </div>
        <button type="button" onClick={onClear} style={changeBtn}>
          Change
        </button>
      </div>
    );
  }

  const showDropdown = open && query.trim().length >= 2;

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <div style={{ position: "relative" }}>
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={(e) => {
            setOpen(true);
            e.currentTarget.style.borderColor = colors.ink;
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = colors.border;
          }}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          autoComplete="off"
          style={inputStyle}
        />
        {isSearching && (
          <div style={spinnerSlot}>
            <Spinner size={16} color={colors.textFaint} />
          </div>
        )}
      </div>

      {showDropdown && (
        <div style={dropdown}>
          {failed ? (
            <div style={messageRow}>
              Address search is unavailable right now — enter coordinates manually below.
            </div>
          ) : results.length === 0 ? (
            <div style={messageRow}>
              {isSearching
                ? "Searching…"
                : "No matches in the service area. Try a nearby landmark, or enter coordinates manually below."}
            </div>
          ) : (
            results.map((r, i) => {
              const unroutable = r.routable === false;
              return (
                <button
                  type="button"
                  key={`${r.osm_type}-${r.osm_id}-${i}`}
                  onClick={() => choose(r)}
                  onMouseEnter={() => setActiveIndex(i)}
                  disabled={unroutable}
                  style={resultRow(i === activeIndex, unroutable)}
                >
                  <div style={resultLabel(unroutable)}>{r.label}</div>
                  {r.context && <div style={resultContext}>{r.context}</div>}
                  {unroutable && (
                    <div style={unroutableNote}>
                      We don't cover this area yet — it's too far from any road our
                      drivers can reach.
                    </div>
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

const inputStyle: CSSProperties = {
  width: "100%",
  height: 46,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  background: colors.surface,
  padding: "0 40px 0 14px",
  fontSize: 16,
  outline: "none",
  transition: "border-color .16s",
  color: colors.text,
};
const spinnerSlot: CSSProperties = {
  position: "absolute",
  right: 14,
  top: "50%",
  transform: "translateY(-50%)",
  display: "flex",
};
const dropdown: CSSProperties = {
  position: "absolute",
  top: "calc(100% + 6px)",
  left: 0,
  right: 0,
  zIndex: 30,
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  boxShadow: shadow.lifted,
  maxHeight: 300,
  overflowY: "auto",
};
const messageRow: CSSProperties = {
  padding: "14px 16px",
  fontSize: 14.5,
  lineHeight: 1.45,
  color: colors.textMuted,
};
function resultRow(active: boolean, unroutable: boolean): CSSProperties {
  return {
    display: "block",
    width: "100%",
    textAlign: "left",
    padding: "10px 16px",
    border: "none",
    borderBottom: `1px solid ${colors.border}`,
    background: active && !unroutable ? colors.surfaceMuted : colors.surface,
    cursor: unroutable ? "default" : "pointer",
    // Greyed out, but still legible — the point is to explain, not to hide.
    opacity: unroutable ? 0.55 : 1,
  };
}
function resultLabel(unroutable: boolean): CSSProperties {
  return {
    fontSize: 15,
    fontWeight: 600,
    color: unroutable ? colors.textMuted : colors.text,
    marginBottom: 2,
  };
}
const resultContext: CSSProperties = {
  fontSize: 13.5,
  color: colors.textFaint,
};
const unroutableNote: CSSProperties = {
  fontSize: 12.5,
  lineHeight: 1.4,
  color: colors.textMuted,
  marginTop: 5,
  fontFamily: font.sans,
};
const chosenBox: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  padding: "11px 14px",
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  background: colors.surfaceMuted,
};
const chosenLabel: CSSProperties = {
  fontSize: 15,
  fontWeight: 600,
  color: colors.text,
  marginBottom: 3,
};
const chosenCoords: CSSProperties = {
  fontSize: 12.5,
  color: colors.textFaint,
  fontFamily: font.mono,
};
const changeBtn: CSSProperties = {
  flexShrink: 0,
  height: 34,
  padding: "0 14px",
  borderRadius: radius.sm,
  border: `1px solid ${colors.border}`,
  background: colors.surface,
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
  color: colors.textMuted,
};
