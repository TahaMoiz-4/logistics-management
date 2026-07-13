/**
 * Shared React Query hooks for reference data used across screens.
 * Enums and customers change rarely, so they're cached generously.
 */
import { useQuery } from "@tanstack/react-query";
import { customersApi, metaApi } from "./endpoints";

export function useEnums() {
  return useQuery({
    queryKey: ["meta", "enums"],
    queryFn: () => metaApi.enums(),
    staleTime: 60 * 60 * 1000, // 1h — enums are effectively static
  });
}

export function useCustomers() {
  return useQuery({
    queryKey: ["customers"],
    queryFn: () => customersApi.list(),
    staleTime: 60 * 1000,
  });
}
