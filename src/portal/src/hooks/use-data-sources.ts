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
  type ManualSyncResult,
  type SafeApiError,
  type SafeConnection,
  type TabularFile,
  type TabularFileList,
  type TabularProfileResponse,
  type TabularReviewEdit,
} from "@/lib/data-sources";

export class SafeApiHttpError extends Error {
  code: string;
  requestId: string;
  fieldErrors?: SafeApiError["field_errors"];
  reason?: string;
  statusClass?: string;
  reasonClass?: string;
  replayed: boolean;

  constructor(err: SafeApiError) {
    super(err.code);
    this.name = "SafeApiHttpError";
    this.code = err.code;
    this.requestId = err.request_id;
    this.fieldErrors = err.field_errors;
    this.reason = err.reason;
    this.statusClass = err.status_class;
    this.reasonClass = err.reason_class;
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

export interface ManualSyncMutationResult {
  result: ManualSyncResult;
  replayed: boolean;
}

/**
 * Manual Blob sync trigger. Each call carries a fresh Idempotency-Key unless one
 * is supplied, so every click is a distinct intent; a success refreshes the
 * connection's last-run status. The response is a safe trigger descriptor, not
 * a connection, which is why this is not a `useDataSourceMutation` action.
 */
export function useManualSyncMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      connectionId: string;
      idempotencyKey?: string;
    }): Promise<ManualSyncMutationResult> => {
      const res = await authFetch(`/api/v1/data-sources/${input.connectionId}/sync`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": input.idempotencyKey ?? newIdempotencyKey(),
        },
        body: "{}",
      });
      if (!res.ok) await throwForStatus(res);
      return { result: (await res.json()) as ManualSyncResult, replayed: isReplayed(res) };
    },
    onSuccess: (_data, input) => {
      queryClient.invalidateQueries({ queryKey: ["data-source", input.connectionId] });
      queryClient.invalidateQueries({ queryKey: ["data-sources"] });
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

/* ------------------------------------------------------------------------
 * Uploaded tabular files (ADR-018). Every mutation carries a fresh
 * Idempotency-Key unless one is supplied.
 * -------------------------------------------------------------------------*/

const FILES_PATH = "/api/v1/data-sources/files";
const IN_FLIGHT = new Set(["profiling", "publishing"]);

export function useTabularFiles() {
  return useQuery<TabularFileList>({
    queryKey: ["tabular-files"],
    queryFn: async () => {
      const res = await authFetch(FILES_PATH);
      if (!res.ok) await throwForStatus(res);
      const body = (await res.json()) as Partial<TabularFileList>;
      return { enabled: body.enabled !== false, files: Array.isArray(body.files) ? body.files : [] };
    },
    retry: false,
    // Poll only while a version is being profiled or published.
    refetchInterval: (query) => {
      const files = query.state.data?.files ?? [];
      const busy = files.some((f) => IN_FLIGHT.has(f.status) || (f.pending !== null && IN_FLIGHT.has(f.pending.status)));
      return busy ? 3000 : false;
    },
  });
}

export function useTabularProfile(fileId: string | null, version: number | null) {
  return useQuery<TabularProfileResponse>({
    queryKey: ["tabular-profile", fileId, version],
    enabled: Boolean(fileId && version),
    queryFn: async () => {
      const res = await authFetch(`${FILES_PATH}/${fileId}/versions/${version}/profile`);
      if (!res.ok) await throwForStatus(res);
      return res.json() as Promise<TabularProfileResponse>;
    },
  });
}

export function useTabularUpload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { file: File; fileId?: string; sheet?: string; idempotencyKey?: string }) => {
      const form = new FormData();
      form.append("file", input.file);
      if (input.sheet) form.append("sheet", input.sheet);
      const path = input.fileId ? `${FILES_PATH}/${input.fileId}/versions` : FILES_PATH;
      const res = await authFetch(path, {
        method: "POST",
        headers: { "Idempotency-Key": input.idempotencyKey ?? newIdempotencyKey() },
        body: form,
      });
      if (!res.ok) await throwForStatus(res);
      return res.json() as Promise<TabularFile>;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tabular-files"] }),
  });
}

export function useTabularReview(fileId: string, version: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { edit: TabularReviewEdit; idempotencyKey?: string }) => {
      const res = await authFetch(`${FILES_PATH}/${fileId}/versions/${version}/review`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": input.idempotencyKey ?? newIdempotencyKey(),
        },
        body: JSON.stringify(input.edit),
      });
      if (!res.ok) await throwForStatus(res);
      return res.json() as Promise<TabularProfileResponse>;
    },
    onSuccess: (data) => queryClient.setQueryData(["tabular-profile", fileId, version], data),
  });
}

export function useTabularPublish(fileId: string, version: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input?: { idempotencyKey?: string }) => {
      const res = await authFetch(`${FILES_PATH}/${fileId}/versions/${version}/publish`, {
        method: "POST",
        headers: { "Idempotency-Key": input?.idempotencyKey ?? newIdempotencyKey() },
      });
      if (!res.ok) await throwForStatus(res);
      return res.json() as Promise<{ file: TabularFile; version: number; status: string }>;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tabular-files"] }),
  });
}

export function useTabularDelete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { fileId: string; idempotencyKey?: string }) => {
      const res = await authFetch(`${FILES_PATH}/${input.fileId}`, {
        method: "DELETE",
        headers: { "Idempotency-Key": input.idempotencyKey ?? newIdempotencyKey() },
      });
      if (!res.ok) await throwForStatus(res);
      return res.json() as Promise<{ id: string; status: string }>;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tabular-files"] }),
  });
}
