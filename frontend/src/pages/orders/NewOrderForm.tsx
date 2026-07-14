/**
 * "New order" slide-over form. Wired to POST /v1/orders.
 *
 * Backend requirements (verified against the live API, not just the design):
 *   - customer_id + service_date are required.
 *   - the order MUST carry a location (lat/lng) — the backend does NOT inherit
 *     it from the customer, so we collect coordinates, prefilling from the
 *     customer's saved location when one exists.
 *   - timewindow_start/end are full datetimes, so we combine the picked time
 *     with the service date into an ISO string before sending.
 */
import { useEffect, useMemo, useState, type CSSProperties, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SlideOver } from "@/components/Modal";
import { Field, SelectInput, SkillChips, TextInput } from "@/components/form/Fields";
import { Spinner } from "@/components/Spinner";
import { useToast } from "@/components/Toast";
import { ordersApi } from "@/api/endpoints";
import { useCustomers, useEnums } from "@/api/queries";
import { ApiError } from "@/api/client";
import type { OrderCreate } from "@/api/types";
import { colors, radius } from "@/theme/tokens";

interface Props {
  open: boolean;
  onClose: () => void;
  /** Default service date (from the currently viewed date/filter). */
  defaultDate?: string;
}

export function NewOrderForm({ open, onClose, defaultDate }: Props) {
  const toast = useToast();
  const qc = useQueryClient();
  const { data: customers } = useCustomers();
  const { data: enums } = useEnums();

  const today = defaultDate ?? new Date().toISOString().slice(0, 10);

  const [customerId, setCustomerId] = useState<string>("");
  const [serviceDate, setServiceDate] = useState(today);
  const [priority, setPriority] = useState("normal");
  const [windowStart, setWindowStart] = useState("");
  const [windowEnd, setWindowEnd] = useState("");
  const [duration, setDuration] = useState("30");
  const [skills, setSkills] = useState<string[]>([]);
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Default the customer once the list loads.
  const resolvedCustomerId = customerId || (customers?.[0]?.id ? String(customers[0].id) : "");

  const skillOptions = enums?.applicable_skills ?? [];
  const priorityOptions = enums?.order_priority ?? ["low", "normal", "high", "urgent"];

  const selectedCustomer = useMemo(
    () => customers?.find((c) => String(c.id) === resolvedCustomerId),
    [customers, resolvedCustomerId],
  );

  // Prefill coordinates from the customer's saved location when they have one
  // (and the user hasn't already typed their own).
  useEffect(() => {
    if (selectedCustomer?.lat != null && selectedCustomer?.lng != null) {
      setLat((cur) => (cur ? cur : String(selectedCustomer.lat)));
      setLng((cur) => (cur ? cur : String(selectedCustomer.lng)));
    }
  }, [selectedCustomer]);

  const mutation = useMutation({
    mutationFn: (body: OrderCreate) => ordersApi.create(body),
    onSuccess: (order) => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.show(`Order ORD-${order.id} created`);
      reset();
      onClose();
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Could not create the order.");
    },
  });

  function reset() {
    setCustomerId("");
    setServiceDate(today);
    setPriority("normal");
    setWindowStart("");
    setWindowEnd("");
    setDuration("30");
    setSkills([]);
    setLat("");
    setLng("");
    setNotes("");
    setFormError(null);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!resolvedCustomerId) {
      setFormError("Pick a customer.");
      return;
    }
    if (!serviceDate) {
      setFormError("Pick a service date.");
      return;
    }
    if ((windowStart && !windowEnd) || (!windowStart && windowEnd)) {
      setFormError("Provide both ends of the time window, or leave both blank.");
      return;
    }
    const latNum = lat.trim() === "" ? null : Number(lat);
    const lngNum = lng.trim() === "" ? null : Number(lng);
    if (latNum == null || lngNum == null || Number.isNaN(latNum) || Number.isNaN(lngNum)) {
      setFormError("This order needs a location. Enter latitude and longitude.");
      return;
    }
    const body: OrderCreate = {
      customer_id: Number(resolvedCustomerId),
      service_date: serviceDate,
      priority,
      required_skills: skills,
      service_duration_min: duration ? Number(duration) : null,
      // Backend wants full datetimes: pin the picked clock time to the service date.
      timewindow_start: windowStart ? `${serviceDate}T${windowStart}:00` : null,
      timewindow_end: windowEnd ? `${serviceDate}T${windowEnd}:00` : null,
      lat: latNum,
      lng: lngNum,
      notes: notes.trim() || null,
    };
    mutation.mutate(body);
  }

  const submitting = mutation.isPending;

  return (
    <SlideOver
      open={open}
      title="New order"
      subtitle="Schedule a service visit for a customer"
      onClose={submitting ? () => {} : onClose}
      footer={
        <>
          <button type="button" style={cancelBtn} onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button type="submit" form="new-order-form" style={submitBtn(submitting)} disabled={submitting}>
            {submitting && <Spinner size={16} color={colors.inkOnDark} track="rgba(245,245,242,.35)" />}
            {submitting ? "Creating…" : "Create order"}
          </button>
        </>
      }
    >
      <form id="new-order-form" onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        <Field label="Customer" required>
          <SelectInput value={resolvedCustomerId} onChange={(e) => setCustomerId(e.target.value)}>
            {!customers && <option>Loading…</option>}
            {customers?.length === 0 && <option value="">No customers yet</option>}
            {customers?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </SelectInput>
        </Field>

        <div style={row2}>
          <Field label="Service date" required>
            <TextInput type="date" value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} />
          </Field>
          <Field label="Priority">
            <SelectInput value={priority} onChange={(e) => setPriority(e.target.value)}>
              {priorityOptions.map((p) => (
                <option key={p} value={p} style={{ textTransform: "capitalize" }}>
                  {p}
                </option>
              ))}
            </SelectInput>
          </Field>
        </div>

        <div style={row2}>
          <Field label="Window start" hint="optional">
            <TextInput type="time" value={windowStart} onChange={(e) => setWindowStart(e.target.value)} />
          </Field>
          <Field label="Window end" hint="optional">
            <TextInput type="time" value={windowEnd} onChange={(e) => setWindowEnd(e.target.value)} />
          </Field>
        </div>

        <Field label="Service duration (min)">
          <TextInput
            type="number"
            min={5}
            step={5}
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
          />
        </Field>

        <Field label="Required skills" hint="the solver only assigns workers who have these">
          <SkillChips options={skillOptions} value={skills} onChange={setSkills} />
        </Field>

        <div style={row2}>
          <Field label="Latitude" required>
            <TextInput
              type="number"
              step="any"
              inputMode="decimal"
              placeholder="24.8607"
              value={lat}
              onChange={(e) => setLat(e.target.value)}
            />
          </Field>
          <Field label="Longitude" required>
            <TextInput
              type="number"
              step="any"
              inputMode="decimal"
              placeholder="67.0011"
              value={lng}
              onChange={(e) => setLng(e.target.value)}
            />
          </Field>
        </div>
        {selectedCustomer?.lat == null && (
          <div style={locationNote}>
            {selectedCustomer?.name ?? "This customer"} has no saved location — enter the visit
            coordinates for this order.
          </div>
        )}

        <Field label="Notes" hint="optional">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            style={textareaStyle}
            placeholder="Anything the worker should know…"
          />
        </Field>

        {formError && <div style={errorBox}>{formError}</div>}
      </form>
    </SlideOver>
  );
}

const row2: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 };
const locationNote: CSSProperties = {
  padding: "11px 14px",
  borderRadius: radius.md,
  background: colors.surfaceMuted,
  border: `1px dashed ${colors.border}`,
  fontSize: 14.5,
  lineHeight: 1.45,
  color: colors.textMuted,
};
const textareaStyle: CSSProperties = {
  width: "100%",
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  background: colors.surface,
  padding: "12px 14px",
  fontSize: 16,
  outline: "none",
  resize: "vertical",
  fontFamily: "inherit",
  color: colors.text,
};
const errorBox: CSSProperties = {
  fontSize: 15,
  color: "#b42318",
  background: "#fef3f2",
  border: "1px solid #fecdca",
  borderRadius: radius.md,
  padding: "10px 14px",
};
const cancelBtn: CSSProperties = {
  height: 44,
  padding: "0 18px",
  borderRadius: radius.md,
  border: `1px solid ${colors.border}`,
  background: colors.surface,
  fontSize: 16,
  fontWeight: 600,
  cursor: "pointer",
  color: colors.text,
};
function submitBtn(disabled: boolean): CSSProperties {
  return {
    height: 44,
    padding: "0 20px",
    borderRadius: radius.md,
    border: "none",
    background: colors.ink,
    color: colors.inkOnDark,
    fontSize: 16,
    fontWeight: 700,
    cursor: disabled ? "default" : "pointer",
    opacity: disabled ? 0.85 : 1,
    display: "flex",
    alignItems: "center",
    gap: 8,
  };
}
