import { useQuery } from "@tanstack/react-query";
import { ordersApi, routePlansApi } from "@/api/endpoints";

export function usePlanList() {
  return useQuery({
    queryKey: ["route-plans"],
    queryFn: () => routePlansApi.list(),
  });
}

export function usePlan(id: number, options?: { refetchInterval?: number | false }) {
  return useQuery({
    queryKey: ["route-plans", id],
    queryFn: () => routePlansApi.get(id),
    refetchInterval: options?.refetchInterval,
  });
}

export function useServableOrders() {
  return useQuery({
    queryKey: ["orders", "servable"],
    queryFn: () => ordersApi.servable(),
  });
}

/** All the result payloads for a solved plan, fetched together. */
export function usePlanResults(id: number, enabled: boolean) {
  const mapData = useQuery({
    queryKey: ["route-plans", id, "map-data"],
    queryFn: () => routePlansApi.mapData(id),
    enabled,
  });
  const diagnostics = useQuery({
    queryKey: ["route-plans", id, "diagnostics"],
    queryFn: () => routePlansApi.diagnostics(id),
    enabled,
  });
  const workerAssignments = useQuery({
    queryKey: ["route-plans", id, "worker-assignments"],
    queryFn: () => routePlansApi.workerAssignments(id),
    enabled,
  });
  const unserved = useQuery({
    queryKey: ["route-plans", id, "unserved"],
    queryFn: () => routePlansApi.unserved(id),
    enabled,
  });
  return { mapData, diagnostics, workerAssignments, unserved };
}
