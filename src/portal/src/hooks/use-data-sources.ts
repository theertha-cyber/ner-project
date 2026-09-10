"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import {
  buildCollectionQuery,
  isReplayed,
  newIdempotencyKey,
  parseSafeError,
  type CollectionQuery,
  type ConnectionPage,
  type ContractDraft,
  type ContractHistory,
  type SafeApiError,
  type SafeConnection,
} from "@/lib/data-sources";

export class SafeApiHttpError extends Error {
  code: string;
  requestId: string;
  fieldErrors?: SafeApiError["field_errors"];
  reason?: string;
  replayed: boolean;

  constructor(err: SafeApiError) {
    super(err.code);
    this.name = "SafeApiHttpError";
    this.code = err.code;
    this.requestId = err.request_id;
    this.fieldErrors = err.field_errors;
    this.reason = err.reason;
    this.replayed = err.replayed ?? false;
  }
}

async function throwForStatus(res: Response): Promise<never> {
  throw new SafeApiHttpError(await parseSafeError(res));
}

export function useDataSourceCollection(query: CollectionQuery) {
  const qs = buildCollectionQuery(query);
  return useQuery<ConnectionPage>({
    queryKey: ["data-sources", qs],
    queryFn: async () => {
      const res = await authFetch(`/api/v1/data-sources?${qs}`);
      if (!res.ok) await throwForStatus(res);
      return res.json() as Promise<ConnectionPage>;
    },
    placeholderData: (prev) => prev,
  });
}

export function useDataSource(connectionId: string | null) {
  return useQuery<SafeConnection>({
    queryKey: ["data-source", connectionId],
    enabled: Boolean(connectionId),
    queryFn: async () => {
      const res = await authFetch(`/api/v1/data-sources/${connectionId}`);
      if (!res.ok) await throwForStatus(res);
      return res.json() as Promise<SafeConnection>;
    },
  });
}

export type LifecycleAction =
  | "create"
  | "update"
  | "test"
  | "activate"
  | "pause"
  | "replace"
  | "retire";

export interface MutationResult {
  connection: SafeConnection;
  replayed: boolean;
}

async function sendMutation(
  method: string,
  path: string,
  body: unknown,
  idempotencyKey: string,
): Promise<MutationResult> {
  const res = await authFetch(path, {
    method,
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(body),
  });
  if (!res.ok) await throwForStatus(res);
  return { connection: (await res.json()) as SafeConnection, replayed: isReplayed(res) };
}

export function useDataSourceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      action: LifecycleAction;
      connectionId?: string;
      body: unknown;
      idempotencyKey?: string;
    }): Promise<MutationResult> => {
      const key = input.idempotencyKey ?? newIdempotencyKey();
      switch (input.action) {
        case "create":
          return sendMutation("POST", "/api/v1/data-sources", input.body, key);
        case "update":
          return sendMutation("PATCH", `/api/v1/data-sources/${input.connectionId}`, input.body, key);
        case "replace":
          return sendMutation("POST", `/api/v1/data-sources/${input.connectionId}/replace`, input.body, key);
        case "test":
          return sendMutation("POST", `/api/v1/data-sources/${input.connectionId}/test`, input.body, key);
        case "activate":
          return sendMutation("POST", `/api/v1/data-sources/${input.connectionId}/activate`, input.body, key);
        case "pause":
          return sendMutation("POST", `/api/v1/data-sources/${input.connectionId}/pause`, input.body, key);
        case "retire":
          return sendMutation("POST", `/api/v1/data-sources/${input.connectionId}/retire`, input.body, key);
      }
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["data-sources"] });
      queryClient.setQueryData(["data-source", result.connection.id], result.connection);
    },
  });
}

export function useSchemaContracts(connectionId: string | null, page: number, pageSize = 20) {
  return useQuery<ContractHistory>({
    queryKey: ["schema-contracts", connectionId, page, pageSize],
    enabled: Boolean(connectionId),
    queryFn: async () => {
      const res = await authFetch(
        `/api/v1/data-sources/${connectionId}/contracts?page=${page}&page_size=${pageSize}`,
      );
      if (!res.ok) await throwForStatus(res);
      return res.json() as Promise<ContractHistory>;
    },
    placeholderData: (prev) => prev,
  });
}

export async function uploadContract(
  connectionId: string,
  document: unknown,
  idempotencyKey: string = newIdempotencyKey(),
): Promise<ContractDraft> {
  const res = await authFetch(`/api/v1/data-sources/${connectionId}/contracts`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(document),
  });
  if (!res.ok) await throwForStatus(res);
  return res.json() as Promise<ContractDraft>;
}

export async function publishContract(
  connectionId: string,
  version: number,
  idempotencyKey: string = newIdempotencyKey(),
): Promise<{ version: number }> {
  const res = await authFetch(`/api/v1/data-sources/${connectionId}/contracts/${version}/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: "{}",
  });
  if (!res.ok) await throwForStatus(res);
  return res.json() as Promise<{ version: number }>;
}
