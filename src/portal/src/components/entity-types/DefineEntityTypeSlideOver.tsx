"use client";

import { useState, useEffect } from "react";
import { SlideOver } from "@/components/ui";
import { useToast } from "@/hooks/use-toast";
import { useCreateEntityType } from "@/hooks/use-create-entity-type";
import { useUpdateEntityType } from "@/hooks/use-update-entity-type";
import type { EntityType } from "@/types/entity-types";

const BASE_LABELS = ["PER", "ORG", "LOC", "MISC"] as const;

export interface DefineEntityTypeSlideOverProps {
  open: boolean;
  onClose: () => void;
  editTarget: EntityType | null;
}

export function DefineEntityTypeSlideOver({ open, onClose, editTarget }: DefineEntityTypeSlideOverProps) {
  const { toast } = useToast();
  const createMutation = useCreateEntityType();
  const updateMutation = useUpdateEntityType();

  const isEdit = editTarget !== null;

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [examples, setExamples] = useState("");
  const [selectedLabel, setSelectedLabel] = useState<string>(BASE_LABELS[0]);
  const [requiredFlag, setRequiredFlag] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (editTarget) {
      setName(editTarget.name);
      setDescription(editTarget.description);
      setExamples(editTarget.examples.join(", "));
      const firstKey = Object.keys(editTarget.base_label_mapping)[0];
      setSelectedLabel(firstKey ?? BASE_LABELS[0]);
      setRequiredFlag(editTarget.required_flag);
    } else {
      setName("");
      setDescription("");
      setExamples("");
      setSelectedLabel(BASE_LABELS[0]);
      setRequiredFlag(false);
    }
  }, [open, editTarget]);

  function buildPayload() {
    return {
      description,
      examples: examples
        .split(", ")
        .map((s) => s.trim())
        .filter(Boolean),
      base_label_mapping: { [selectedLabel]: [name || editTarget?.name || ""] },
      required_flag: requiredFlag,
    };
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (isEdit && editTarget) {
      updateMutation.mutate(
        { entityTypeName: editTarget.name, payload: buildPayload() },
        {
          onSuccess: () => {
            toast("Entity type updated successfully");
            onClose();
          },
          onError: (err) => {
            toast(err.message ?? "Update failed", "bad");
          },
        },
      );
    } else {
      createMutation.mutate(
        { name, ...buildPayload() },
        {
          onSuccess: () => {
            toast("Entity type created successfully");
            onClose();
          },
          onError: (err) => {
            toast(err.message ?? "Create failed", "bad");
          },
        },
      );
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <SlideOver open={open} onClose={onClose} width={460}>
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-border px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-primary">
              {isEdit ? "Edit entity type" : "Create entity type"}
            </h2>
            <p
              className="text-secondary mt-0.5"
              style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}
            >
              POST /api/v1/entity-types
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-secondary hover:text-primary transition-colors mt-0.5"
          >
            ✕
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-1 flex-col gap-5 overflow-y-auto px-5 py-5">
          {/* NAME */}
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-secondary">
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={isEdit}
              placeholder="vendor_name"
              className="w-full rounded border border-border px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            />
          </div>

          {/* DESCRIPTION */}
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-secondary">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Name of a vendor / supplier"
              className="w-full rounded border border-border px-3 py-2 text-sm"
            />
          </div>

          {/* EXAMPLES */}
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-secondary">
              Examples
            </label>
            <input
              type="text"
              value={examples}
              onChange={(e) => setExamples(e.target.value)}
              placeholder="Acme Supplies, Global Tech Ltd"
              className="w-full rounded border border-border px-3 py-2 text-sm"
            />
          </div>

          {/* BASE MODEL LABEL */}
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-secondary">
              Base Model Label
            </label>
            <div className="flex gap-2">
              {BASE_LABELS.map((label) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => setSelectedLabel(label)}
                  className={[
                    "rounded px-3 py-1.5 text-xs font-medium border transition-colors",
                    selectedLabel === label
                      ? "border-brand-primary bg-brand-primary text-white"
                      : "border-border hover:border-brand-primary hover:text-brand-primary",
                  ].join(" ")}
                  aria-pressed={selectedLabel === label}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* REQUIRED FLAG */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-primary">Required flag</p>
              <p className="text-xs text-secondary">enforce presence at extraction</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={requiredFlag}
              onClick={() => setRequiredFlag((v) => !v)}
              className={[
                "relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors",
                requiredFlag ? "bg-brand-primary" : "bg-gray-200",
              ].join(" ")}
            >
              <span
                className={[
                  "pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transition-transform",
                  requiredFlag ? "translate-x-4" : "translate-x-0",
                ].join(" ")}
              />
            </button>
          </div>

          {/* Save button */}
          <div className="mt-auto pt-2">
            <button
              type="submit"
              disabled={isPending}
              className="w-full rounded-lg bg-brand-primary px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isPending
                ? "Saving..."
                : isEdit
                  ? "Save changes"
                  : "Create entity type"}
            </button>
          </div>
        </form>
      </div>
    </SlideOver>
  );
}
