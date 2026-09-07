/**
 * Debounced address search backed by /v1/geocode/search.
 *
 * Three problems come with searching on every keystroke, and this hook exists
 * to solve them:
 *
 *   1. VOLUME — "askari 4 karachi" is 16 keystrokes. Firing a request per
 *      keystroke wastes 15 of them and hammers Komoot's free Photon instance.
 *      Debouncing collapses a burst of typing into one request.
 *
 *   2. ORDERING — requests are independent HTTP calls, and the network makes no
 *      promise about the order they return in. Type "ask" then "aska": if
 *      "ask" resolves LAST, its stale results overwrite the fresher ones and
 *      the dropdown shows suggestions for a prefix the user already typed past.
 *      React Query keys each query by its search term, so a late response lands
 *      under its own key rather than clobbering the current one, and the
 *      AbortSignal cancels the request that is no longer needed.
 *
 *   3. REPEATS — backspacing from "aska" to "ask" should be instant. React
 *      Query serves that from cache with no request at all.
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { geocodeApi } from "@/api/endpoints";
import type { GeocodeResult } from "@/api/types";

/** Below this, results are too broad to be useful (and the API rejects <2). */
const MIN_QUERY_LENGTH = 2;
/** Pause after typing stops before we call the API. */
const DEBOUNCE_MS = 250;

export function useAddressSearch(query: string): {
  results: GeocodeResult[];
  isSearching: boolean;
  failed: boolean;
} {
  const debounced = useDebouncedValue(query.trim(), DEBOUNCE_MS);
  const enabled = debounced.length >= MIN_QUERY_LENGTH;

  const { data, isFetching, isError } = useQuery({
    queryKey: ["geocode", debounced],
    queryFn: ({ signal }) => geocodeApi.search(debounced, signal),
    enabled,
    // OSM data barely moves within a session, and the backend caches in Redis
    // anyway — so never refetch a term we already have.
    staleTime: 5 * 60 * 1000,
    retry: false, // a failed keystroke is not worth retrying; the next one supersedes it
  });

  return {
    results: data?.results ?? [],
    // Only "searching" once the debounce has settled, so the spinner does not
    // flicker on every character.
    isSearching: enabled && isFetching,
    failed: isError,
  };
}

/**
 * `value`, delayed until it has stopped changing for `delayMs`.
 *
 * The cleanup return is what makes this a debounce rather than just a delay:
 * the effect re-runs on every change to `value`, and React tears down the
 * previous run first — so an in-flight timer is cleared before a new one
 * starts. Only the last keystroke of a burst survives to commit.
 */
function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
