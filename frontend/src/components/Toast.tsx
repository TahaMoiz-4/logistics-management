/**
 * App-wide toast. A single bottom-center notification, matching the prototype.
 * Any component calls useToast().show("message"). Auto-dismisses.
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { colors, radius, shadow } from "@/theme/tokens";

interface ToastApi {
  show: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  const show = useCallback((msg: string) => {
    setMessage(msg);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setMessage(null), 3400);
  }, []);

  const api = useMemo<ToastApi>(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      {message && (
        <div className="ng-fade" style={toastStyle} role="status">
          <span style={pip} />
          {message}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}

const toastStyle: CSSProperties = {
  position: "fixed",
  bottom: 26,
  left: "50%",
  transform: "translateX(-50%)",
  zIndex: 100,
  background: colors.ink,
  color: colors.inkOnDark,
  padding: "13px 20px",
  borderRadius: radius.lg,
  fontSize: 13,
  fontWeight: 500,
  boxShadow: shadow.lifted,
  display: "flex",
  alignItems: "center",
  gap: 10,
};
const pip: CSSProperties = {
  width: 8,
  height: 8,
  borderRadius: "50%",
  background: colors.accent,
};
