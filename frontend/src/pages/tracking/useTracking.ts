import { useQuery } from "@tanstack/react-query";
import { trackingApi } from "@/api/endpoints";

/** Live positions — polled every 3s to match the console's "live" cadence. */
export function useLiveTracking() {
  return useQuery({
    queryKey: ["tracking", "live"],
    queryFn: () => trackingApi.live(),
    refetchInterval: 3000,
  });
}

/** Availability roster — polled less often; it changes slowly. */
export function useAvailabilityRoster() {
  return useQuery({
    queryKey: ["tracking", "availability"],
    queryFn: () => trackingApi.availability(),
    refetchInterval: 30000,
  });
}
