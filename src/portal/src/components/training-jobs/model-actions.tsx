"use client";

import type { ModelVersion } from "@/types/model-registry";
import { Spinner } from "@/components/ui";
import { useToast } from "@/hooks";
import { useAuth } from "@/lib/auth";
import { usePromoteModel } from "@/hooks/use-promote-model";
import { useDemoteModel } from "@/hooks/use-demote-model";
import { useWarmupModel } from "@/hooks/use-warmup-model";

export interface ModelActionsProps {
  model: ModelVersion | null | undefined;
}

export function ModelActions({ model }: ModelActionsProps) {
  const { user } = useAuth();
  const { toast } = useToast();
  const promoteMutation = usePromoteModel();
  const demoteMutation = useDemoteModel();
  const warmupMutation = useWarmupModel();

  const isTenantAdmin = user?.role === "tenant_admin";
  const isBaseModel = model?.version_number === 0;

  if (!model || isBaseModel || !isTenantAdmin) return null;

  const canPromote = model.status === "completed";
  const canDemote = model.status === "promoted";

  function handlePromote() {
    promoteMutation.mutate(
      { modelId: model!.id },
      {
        onSuccess: () => toast("Model promoted successfully"),
        onError: (err) => toast(err.message, "bad"),
      },
    );
  }

  function handleDemote() {
    demoteMutation.mutate(
      { modelId: model!.id },
      {
        onSuccess: () => toast("Model demoted successfully"),
        onError: (err) => toast(err.message, "bad"),
      },
    );
  }

  function handleWarmup() {
    warmupMutation.mutate(
      { modelId: model!.id },
      {
        onSuccess: () => toast("Warmup triggered successfully"),
        onError: (err) => toast(err.message, "bad"),
      },
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {canPromote && (
        <button
          type="button"
          onClick={handlePromote}
          disabled={promoteMutation.isPending}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-body text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--primary)" }}
        >
          {promoteMutation.isPending && <Spinner size="sm" />}
          Promote
        </button>
      )}
      {canDemote && (
        <button
          type="button"
          onClick={handleDemote}
          disabled={demoteMutation.isPending}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-body text-sm font-medium disabled:opacity-50"
          style={{ border: "1px solid var(--line)", color: "var(--ink-2)" }}
        >
          {demoteMutation.isPending && <Spinner size="sm" />}
          Demote
        </button>
      )}
      <button
        type="button"
        onClick={handleWarmup}
        disabled={warmupMutation.isPending}
        className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-body text-sm font-medium disabled:opacity-50"
        style={{ border: "1px solid var(--line)", color: "var(--ink-2)" }}
      >
        {warmupMutation.isPending && <Spinner size="sm" />}
        Warmup
      </button>
    </div>
  );
}
