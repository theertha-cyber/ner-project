"use client";

import { useState } from "react";
import { useEntityTypes } from "@/hooks/use-entity-types";
import { useToggleEntityType } from "@/hooks/use-toggle-entity-type";
import { useToast } from "@/hooks/use-toast";
import { EntityTypeCard } from "./EntityTypeCard";
import { DefineEntityTypeSlideOver } from "./DefineEntityTypeSlideOver";
import type { EntityType } from "@/types/entity-types";

function SkeletonCard() {
  return (
    <div className="rounded-lg border border-border bg-surface p-4 flex flex-col gap-3 animate-pulse">
      <div className="flex items-start gap-3">
        <div className="rounded-md bg-gray-200" style={{ width: 34, height: 34 }} />
        <div className="flex-1 space-y-2">
          <div className="h-3.5 w-32 rounded bg-gray-200" />
          <div className="h-2.5 w-48 rounded bg-gray-200" />
        </div>
      </div>
      <div className="flex gap-2">
        <div className="h-5 w-16 rounded-full bg-gray-200" />
        <div className="h-5 w-12 rounded-full bg-gray-200" />
      </div>
      <div className="h-8 rounded bg-gray-200" />
      <div className="h-4 w-40 rounded bg-gray-200" />
      <div className="flex gap-2 mt-auto pt-1">
        <div className="h-7 w-12 rounded bg-gray-200" />
        <div className="h-7 w-20 rounded bg-gray-200" />
      </div>
    </div>
  );
}

export function EntityTypesPage() {
  const { data, isLoading } = useEntityTypes();
  const toggleMutation = useToggleEntityType();
  const { toast } = useToast();

  const [slideOverOpen, setSlideOverOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<EntityType | null>(null);

  const entityTypes = data?.entity_types ?? [];
  const activeCount = entityTypes.filter((et) => et.is_active).length;

  function openCreate() {
    setEditTarget(null);
    setSlideOverOpen(true);
  }

  function openEdit(entityType: EntityType) {
    setEditTarget(entityType);
    setSlideOverOpen(true);
  }

  function handleToggle(entityType: EntityType) {
    toggleMutation.mutate(
      { name: entityType.name, is_active: !entityType.is_active },
      {
        onSuccess: () => {
          toast(
            entityType.is_active
              ? `${entityType.name} deactivated`
              : `${entityType.name} reactivated`,
          );
        },
        onError: (err) => {
          toast(err.message ?? "Toggle failed", "bad");
        },
      },
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <p
            className="text-secondary mb-1"
            style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}
          >
            /api/v1/entity-types
          </p>
          <h1 className="text-xl font-semibold text-primary">Entity Types</h1>
          {!isLoading && (
            <p className="text-sm text-secondary mt-0.5">
              {activeCount} active / {entityTypes.length}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
        >
          + Define entity type
        </button>
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div
          className="grid gap-3.5"
          style={{ gridTemplateColumns: "repeat(2, 1fr)" }}
        >
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && entityTypes.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-secondary text-sm">
            Define your first entity type to get started
          </p>
        </div>
      )}

      {/* Card grid */}
      {!isLoading && entityTypes.length > 0 && (
        <div
          className="grid gap-3.5"
          style={{ gridTemplateColumns: "repeat(2, 1fr)" }}
        >
          {entityTypes.map((et, i) => (
            <EntityTypeCard
              key={et.id}
              entityType={et}
              index={i}
              onEdit={() => openEdit(et)}
              onToggle={() => handleToggle(et)}
            />
          ))}
        </div>
      )}

      <DefineEntityTypeSlideOver
        open={slideOverOpen}
        onClose={() => setSlideOverOpen(false)}
        editTarget={editTarget}
      />
    </div>
  );
}
