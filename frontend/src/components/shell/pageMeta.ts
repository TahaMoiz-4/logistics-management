import { createContext, useContext, useEffect, type ReactNode } from "react";

export interface PageMeta {
  title: string;
  subtitle: ReactNode;
}

/** Setter provided by AppShell; pages call usePageMeta() to update the header. */
export const PageMetaContext = createContext<((meta: PageMeta) => void) | null>(null);

/** Set the header title/subtitle for the current page. */
export function usePageMeta(title: string, subtitle: ReactNode): void {
  const setMeta = useContext(PageMetaContext);
  useEffect(() => {
    setMeta?.({ title, subtitle });
  }, [setMeta, title, subtitle]);
}
