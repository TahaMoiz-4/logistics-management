/**
 * Settings — currently the demo-data tools.
 *
 * Seeded orders are dated relative to the day the seed ran, and the route-plan
 * picker only lists orders from today onward, so a demo box left alone for a
 * week has nothing solvable in it. This puts the refresh in the console so a
 * salesperson can do it mid-demo instead of asking someone to SSH into the VM.
 *
 * The action is destructive, so it asks for typed confirmation rather than
 * firing on a single click — the one thing worse than a stale demo is wiping a
 * demo halfway through one.
 */
import { useState, type CSSProperties } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { settingsApi } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { Spinner } from "@/components/Spinner";
import { useToast } from "@/components/Toast";
import { colors, font, radius, shadow } from "@/theme/tokens";

const CONFIRM_WORD = "RESET";

export function SettingsPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const [confirmText, setConfirmText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: status, isLoading } = useQuery({
    queryKey: ["settings", "demo-data"],
    queryFn: () => settingsApi.demoDataStatus(),
  });

  const reseed = useMutation({
    mutationFn: () => settingsApi.reseedDemoData(),
    onSuccess: (res) => {
      // Every cached list is now stale — the underlying rows were replaced.
      qc.invalidateQueries();
      setConfirmText("");
      setError(null);
      toast.show(`Demo data refreshed — ${res.orders} orders, ${res.customers} customers`);
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Could not refresh the demo data.");
    },
  });

  const armed = confirmText.trim().toUpperCase() === CONFIRM_WORD;
  const running = reseed.isPending;

  return (
    <div style={{ padding: "28px 32px", maxWidth: 780 }}>
      <h1 style={titleStyle}>Settings</h1>
      <p style={subtitleStyle}>Tools for running and refreshing the demo environment.</p>

      {isLoading && (
        <div style={{ marginTop: 24 }}>
          <Spinner size={20} />
        </div>
      )}

      {!isLoading && status && !status.enabled && (
        <div style={{ ...card, marginTop: 24 }}>
          <div style={cardTitle}>Demo data</div>
          <p style={cardBody}>
            Demo tools are disabled on this deployment. They are switched on only for the
            demo environment, so that live data can never be reset from the console.
          </p>
        </div>
      )}

      {!isLoading && status?.enabled && (
        <div style={{ ...card, marginTop: 24 }}>
          <div style={cardTitle}>Demo data</div>
          <p style={cardBody}>
            Replaces everything in the demo with a fresh set of orders, customers, workers
            and vehicles, dated from today. Use this when the demo looks empty or the
            orders are in the past.
          </p>

          <div style={warningBox}>
            <strong style={{ display: "block", marginBottom: 4 }}>
              This clears the current demo data first.
            </strong>
            All existing orders, customers, workers, vehicles and route plans are removed
            — for both demo companies, not just this one. Your login is unaffected.
          </div>

          {!status.is_admin ? (
            <div style={mutedNote}>Only an admin can refresh the demo data.</div>
          ) : (
            <>
              <label style={{ display: "block", marginTop: 18 }}>
                <span style={confirmLabel}>
                  Type <code style={codeStyle}>{CONFIRM_WORD}</code> to enable the button
                </span>
                <input
                  value={confirmText}
                  onChange={(e) => {
                    setConfirmText(e.target.value);
                    setError(null);
                  }}
                  placeholder={CONFIRM_WORD}
                  disabled={running}
                  style={confirmInput}
                  autoComplete="off"
                />
              </label>

              <button
                type="button"
                onClick={() => reseed.mutate()}
                disabled={!armed || running}
                style={dangerBtn(!armed || running)}
              >
                {running && <Spinner size={16} color="#fff" track="rgba(255,255,255,.35)" />}
                {running ? "Refreshing…" : "Reset & add demo data"}
              </button>

              {error && <div style={errorBox}>{error}</div>}

              {reseed.isSuccess && !error && (
                <div style={successBox}>
                  Demo data refreshed — {reseed.data.orders} orders and{" "}
                  {reseed.data.customers} customers, starting today.
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

const titleStyle: CSSProperties = {
  fontSize: 26,
  fontWeight: 700,
  letterSpacing: "-.02em",
  margin: 0,
  color: colors.text,
};
const subtitleStyle: CSSProperties = {
  fontSize: 15,
  color: colors.textMuted,
  margin: "6px 0 0",
};
const card: CSSProperties = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.lg,
  boxShadow: shadow.card,
  padding: "22px 24px",
};
const cardTitle: CSSProperties = {
  fontSize: 17,
  fontWeight: 700,
  color: colors.text,
  marginBottom: 8,
};
const cardBody: CSSProperties = {
  fontSize: 15,
  lineHeight: 1.55,
  color: colors.textMuted,
  margin: "0 0 16px",
};
const warningBox: CSSProperties = {
  fontSize: 14,
  lineHeight: 1.5,
  color: "#7a2e0e",
  background: "#fff7ed",
  border: "1px solid #fed7aa",
  borderRadius: radius.md,
  padding: "12px 14px",
};
const mutedNote: CSSProperties = {
  marginTop: 16,
  fontSize: 14.5,
  color: colors.textFaint,
};
const confirmLabel: CSSProperties = {
  display: "block",
  fontSize: 14,
  fontWeight: 600,
  color: colors.textMuted,
  marginBottom: 7,
};
const codeStyle: CSSProperties = {
  fontFamily: font.mono,
  fontSize: 13,
  background: colors.surfaceMuted,
  border: `1px solid ${colors.border}`,
  borderRadius: 5,
  padding: "1px 6px",
};
const confirmInput: CSSProperties = {
  width: 220,
  height: 44,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  background: colors.surface,
  padding: "0 14px",
  fontSize: 16,
  fontFamily: font.mono,
  outline: "none",
  color: colors.text,
};
function dangerBtn(disabled: boolean): CSSProperties {
  return {
    marginTop: 16,
    height: 44,
    padding: "0 20px",
    borderRadius: radius.md,
    border: "none",
    background: disabled ? "#e5e5e5" : "#b42318",
    color: disabled ? colors.textFaint : "#fff",
    fontSize: 15.5,
    fontWeight: 700,
    cursor: disabled ? "default" : "pointer",
    display: "flex",
    alignItems: "center",
    gap: 8,
  };
}
const errorBox: CSSProperties = {
  marginTop: 14,
  fontSize: 14.5,
  color: "#b42318",
  background: "#fef3f2",
  border: "1px solid #fecdca",
  borderRadius: radius.md,
  padding: "10px 14px",
};
const successBox: CSSProperties = {
  marginTop: 14,
  fontSize: 14.5,
  color: "#166534",
  background: "#f0fdf4",
  border: "1px solid #bbf7d0",
  borderRadius: radius.md,
  padding: "10px 14px",
};
