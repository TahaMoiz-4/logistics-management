/**
 * Subscribes to the solver's SSE progress stream for a plan and accumulates a
 * live view of the optimization: the objective traces, current iteration/elapsed,
 * a coarse stage, and terminal state.
 *
 * The backend /stream endpoint is unauthenticated (keyed only by plan_id), so a
 * plain EventSource works — no Authorization header needed. Events observed:
 *   loading → progress (many) → persisting → done | error → close
 */
import { useEffect, useRef, useState } from "react";

export type SolveStage = "loading" | "solving" | "persisting" | "done" | "error";

export interface SolverState {
  stage: SolveStage;
  iteration: number;
  elapsedSec: number;
  bestObjective: number | null;
  currentObjective: number | null;
  /** Downsample-friendly traces built as events arrive. */
  bestTrace: number[];
  currentTrace: number[];
  errorMessage: string | null;
}

const INITIAL: SolverState = {
  stage: "loading",
  iteration: 0,
  elapsedSec: 0,
  bestObjective: null,
  currentObjective: null,
  bestTrace: [],
  currentTrace: [],
  errorMessage: null,
};

/** Keep at most this many trace points client-side (the solver runs 100k+ iters). */
const MAX_TRACE = 400;

export function useSolverStream(planId: number, enabled: boolean): SolverState {
  const [state, setState] = useState<SolverState>(INITIAL);
  // Buffer arrays in refs, flush to state on a throttle to avoid re-rendering
  // on every one of thousands of events.
  const best = useRef<number[]>([]);
  const cur = useRef<number[]>([]);
  const latest = useRef<Partial<SolverState>>({});
  const pendingFlush = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    setState(INITIAL);
    best.current = [];
    cur.current = [];
    latest.current = {};

    const es = new EventSource(`/v1/route-plans/${planId}/stream`);

    const flush = () => {
      pendingFlush.current = false;
      setState((s) => ({
        ...s,
        ...latest.current,
        bestTrace: decimate(best.current, MAX_TRACE),
        currentTrace: decimate(cur.current, MAX_TRACE),
      }));
    };
    const scheduleFlush = () => {
      if (pendingFlush.current) return;
      pendingFlush.current = true;
      setTimeout(flush, 120);
    };

    const onProgress = (ev: MessageEvent) => {
      const d = safeParse(ev.data);
      if (!d) return;
      if (typeof d.current_objective === "number") cur.current.push(d.current_objective);
      const bestVal =
        typeof d.best_objective === "number"
          ? d.best_objective
          : best.current.length
            ? best.current[best.current.length - 1]
            : typeof d.current_objective === "number"
              ? d.current_objective
              : null;
      if (bestVal != null) best.current.push(bestVal);
      latest.current = {
        stage: "solving",
        iteration: d.iteration ?? latest.current.iteration ?? 0,
        elapsedSec: d.elapsed_sec ?? latest.current.elapsedSec ?? 0,
        currentObjective: d.current_objective ?? latest.current.currentObjective ?? null,
        bestObjective: bestVal,
      };
      scheduleFlush();
    };

    const setStage = (stage: SolveStage) => {
      latest.current = { ...latest.current, stage };
      scheduleFlush();
    };

    es.addEventListener("loading", () => setStage("loading"));
    es.addEventListener("solving", () => setStage("solving"));
    es.addEventListener("progress", onProgress as EventListener);
    es.addEventListener("best", onProgress as EventListener);
    es.addEventListener("persisting", () => setStage("persisting"));
    es.addEventListener("done", () => {
      latest.current = { ...latest.current, stage: "done" };
      flush();
      es.close();
    });
    es.addEventListener("error", (ev) => {
      // Distinguish a server "error" event (has data) from a transport drop.
      const msg = ev instanceof MessageEvent ? safeParse(ev.data)?.message : null;
      if (msg) {
        latest.current = { ...latest.current, stage: "error", errorMessage: msg };
        flush();
        es.close();
      }
      // transport hiccups: EventSource auto-reconnects, so ignore.
    });
    es.addEventListener("close", () => es.close());

    return () => es.close();
  }, [planId, enabled]);

  return state;
}

function safeParse(raw: string): any | null {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/** Even-stride downsample, always keeping the last point. */
function decimate(arr: number[], max: number): number[] {
  if (arr.length <= max) return arr.slice();
  const step = arr.length / max;
  const out: number[] = [];
  for (let i = 0; i < max; i++) out.push(arr[Math.floor(i * step)]);
  out[out.length - 1] = arr[arr.length - 1];
  return out;
}
