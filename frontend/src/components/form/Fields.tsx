/**
 * Small set of styled form controls shared by all create/edit forms:
 * Field (label wrapper), TextInput, SelectInput, and SkillChips (multi-select).
 * Keeps every form visually consistent with the console.
 */
import type { CSSProperties, ReactNode } from "react";
import { colors, font, radius } from "@/theme/tokens";

export function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <label style={{ display: "block" }}>
      <span style={labelStyle}>
        {label}
        {required && <span style={{ color: colors.accent, marginLeft: 4 }}>*</span>}
      </span>
      {children}
      {hint && <span style={hintStyle}>{hint}</span>}
    </label>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      style={{ ...inputStyle, ...(props.style as CSSProperties) }}
      onFocus={(e) => {
        e.currentTarget.style.borderColor = colors.ink;
        props.onFocus?.(e);
      }}
      onBlur={(e) => {
        e.currentTarget.style.borderColor = colors.border;
        props.onBlur?.(e);
      }}
    />
  );
}

export function SelectInput(
  props: React.SelectHTMLAttributes<HTMLSelectElement> & { children: ReactNode },
) {
  return (
    <select {...props} style={{ ...inputStyle, ...(props.style as CSSProperties) }}>
      {props.children}
    </select>
  );
}

/** Multi-select rendered as toggleable chips. */
export function SkillChips({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const toggle = (skill: string) => {
    onChange(value.includes(skill) ? value.filter((s) => s !== skill) : [...value, skill]);
  };
  if (options.length === 0) {
    return <div style={{ fontSize: 14, color: colors.textFaint }}>No skills configured.</div>;
  }
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {options.map((skill) => {
        const on = value.includes(skill);
        return (
          <button
            type="button"
            key={skill}
            onClick={() => toggle(skill)}
            style={{
              fontSize: 14,
              padding: "6px 12px",
              borderRadius: 9,
              cursor: "pointer",
              textTransform: "capitalize",
              border: `1px solid ${on ? colors.ink : colors.border}`,
              background: on ? colors.ink : colors.surface,
              color: on ? colors.inkOnDark : colors.textMuted,
              transition: "all .15s",
            }}
          >
            {skill.replace(/_/g, " ")}
          </button>
        );
      })}
    </div>
  );
}

const labelStyle: CSSProperties = {
  display: "block",
  fontSize: 14,
  fontWeight: 600,
  color: colors.textMuted,
  marginBottom: 7,
};
const hintStyle: CSSProperties = {
  display: "block",
  fontSize: 12,
  color: colors.textFaint,
  marginTop: 6,
  fontFamily: font.mono,
};
const inputStyle: CSSProperties = {
  width: "100%",
  height: 46,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  background: colors.surface,
  padding: "0 14px",
  fontSize: 16,
  outline: "none",
  transition: "border-color .16s",
  color: colors.text,
};
