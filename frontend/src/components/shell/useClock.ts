import { useEffect, useState } from "react";

/** Live HH:MM:SS PKT clock, matching the prototype's header ticker. */
export function useClock(): string {
  const [clock, setClock] = useState(() => formatNow());
  useEffect(() => {
    const id = setInterval(() => setClock(formatNow()), 1000);
    return () => clearInterval(id);
  }, []);
  return clock;
}

function formatNow(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())} PKT`;
}
