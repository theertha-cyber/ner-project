"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { SchemaProposal } from "@/types/seed-bootstrap";

/** Backend error envelopes come in two shapes; unwrap both rather than surfacing "[object Object]". */
async function errorMessage(res: Response, fallback: string): Promise<string> {
  const body = await res.json().catch(() => null);
  const detail = body?.detail ?? body?.error;
  if (typeof detail === "string") return detail;
  return detail?.message ?? `${fallback}: ${res.status}`;
}

export interface RequestProposalPayload {
  documentIds: string[];
  /** Optional Q&A-pair document (uploaded separately as purpose='qa_pair'). */
  qaPairDocumentId?: string | null;
}

export function useRequestSchemaProposal() {
  const queryClient = useQueryClient();

  return useMutation<{ proposal_id: string }, Error, RequestProposalPayload>({
    mutationFn: async ({ documentIds, qaPairDocumentId }) => {
      const res = await authFetch("/api/v1/schema-proposals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_ids: documentIds,
          ...(qaPairDocumentId ? { qa_pair_document_id: qaPairDocumentId } : {}),
        }),
      });
      if (!res.ok) throw new Error(await errorMessage(res, "Proposal request failed"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schema-proposal"] });
    },
  });
}

/**
 * Poll a proposal until the worker finishes with it.
 *
 * Polling rather than pushing because the generation is a Celery job with no channel back to
 * the browser, and it stops as soon as the status is terminal — a completed proposal does not
 * change, so continuing to ask would be asking a question already answered.
 */
export function useSchemaProposal(proposalId: string | null) {
  return useQuery<SchemaProposal>({
    queryKey: ["schema-proposal", proposalId],
    enabled: !!proposalId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 2000;
    },
    queryFn: async () => {
      const res = await authFetch(`/api/v1/schema-proposals/${proposalId}`);
      if (!res.ok) throw new Error(await errorMessage(res, "Failed to load proposal"));
      return res.json();
    },
  });
}

export interface CandidateEdit {
  candidateId: string;
  name?: string;
  description?: string;
  examples?: string[];
}

export function useEditCandidate() {
  const queryClient = useQueryClient();

  return useMutation<unknown, Error, CandidateEdit>({
    mutationFn: async ({ candidateId, ...changes }) => {
      const res = await authFetch(`/api/v1/schema-proposals/candidates/${candidateId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
      });
      if (!res.ok) throw new Error(await errorMessage(res, "Edit failed"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schema-proposal"] });
    },
  });
}

/**
 * Approve one candidate.
 *
 * The entity type is created server-side through the entity-config API, so the entity types
 * list is invalidated alongside the proposal — a candidate approved here shows up on the Entity
 * Types screen, and a stale cache there would make it look as though nothing happened.
 */
export function useApproveCandidate() {
  const queryClient = useQueryClient();

  return useMutation<unknown, Error, string>({
    mutationFn: async (candidateId) => {
      const res = await authFetch(
        `/api/v1/schema-proposals/candidates/${candidateId}/approve`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(await errorMessage(res, "Approve failed"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schema-proposal"] });
      queryClient.invalidateQueries({ queryKey: ["entity-types"] });
    },
  });
}

export function useRejectCandidate() {
  const queryClient = useQueryClient();

  return useMutation<unknown, Error, string>({
    mutationFn: async (candidateId) => {
      const res = await authFetch(
        `/api/v1/schema-proposals/candidates/${candidateId}/reject`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(await errorMessage(res, "Reject failed"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schema-proposal"] });
    },
  });
}
