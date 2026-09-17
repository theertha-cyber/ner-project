"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import { newIdempotencyKey, parseSafeError, type DataPlaneStatusResponse } from "@/lib/data-sources";
import { SafeApiHttpError } from "./use-data-sources";

async function throwForStatus(res: Response): Promise<never> {
  throw new SafeApiHttpError(await parseSafeError(res));
}

/** The authenticated tenant's own data-plane status (ADR-017, task 13.3).
 * Poll-friendly: a short interval lets `DataPlaneGate` and the settings panel
 * notice provisioning finish or a store recover without a manual refresh. */
export function useDataPlaneStatus(options?: { pollIntervalMs?: number }) {
  return useQuery<DataPlaneStatusResponse>({
    queryKey: ["data-plane"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/data-plane");
      if (!res.ok) await throwForStatus(res);
      return res.json() as Promise<DataPlaneStatusResponse>;
    },
    // `DataPlaneGate` shows a spinner over the whole page until this settles, so the
    // default 1s/2s/4s backoff costs every navigation ~7s. A server answer (403, 409,
    // 503) will say the same thing again; only a request that never got one retries.
    retry: (failureCount, error) => !(error instanceof SafeApiHttpError) && failureCount < 3,
    refetchInterval: options?.pollIntervalMs ?? false,
  });
}

/** `POST /api/v1/data-plane/provision` — the tenant-admin retry after a
 * `provisioning_failed` outcome. */
export function useRetryDataPlaneProvisioning() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (idempotencyKey?: string): Promise<DataPlaneStatusResponse> => {
      const res = await authFetch("/api/v1/data-plane/provision", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey ?? newIdempotencyKey() },
        body: "{}",
      });
      if (!res.ok) await throwForStatus(res);
      return res.json() as Promise<DataPlaneStatusResponse>;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["data-plane"], data);
    },
  });
}
