import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/api/endpoints";

/** Today's dashboard rollup. Polls every 10s to mirror the "live" header note. */
export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard", "today"],
    queryFn: () => dashboardApi.today(),
    refetchInterval: 10_000,
  });
}
