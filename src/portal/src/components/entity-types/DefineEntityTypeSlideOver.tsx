"use client";

import { useState, useEffect } from "react";
import { SlideOver } from "@/components/ui";
import { useToast } from "@/hooks/use-toast";
import { useCreateEntityType } from "@/hooks/use-create-entity-type";
import { useUpdateEntityType } from "@/hooks/use-update-entity-type";
import type { EntityCardinality, EntityType } from "@/types/entity-types";

const BASE_LABELS = ["PER", "ORG", "LOC", "MISC"] as const;

// Explained in query terms rather than schema terms: the admin choosing this does not know
// that `single` means a column on `subject` and `multi` means a child table, and should not
// have to. What they do know is whether a document has one of these or many.
const CARDINALITY_OPTIONS: {
  value: EntityCardinality;
  label: string;
  hint: string;
}[] = [
  { value: "single", label: "Single value", hint: "one value per document" },
  { value: "multi", label: "Multiple values", hint: "many values per document" },
];

// Mirrors `SUPPORTED_KINDS` in `semantic_normalizer.py`. It decides the column type a `single`
// entity type receives, so a numeric or date entity type left at `text` cannot be compared or
// ordered in generated SQL.
const VALUE_KINDS = ["text", "number", "duration", "money", "date", "boolean"] as const;

const DEFAULT_CARDINALITY: EntityCardinality = "multi";
const DEFAULT_VALUE_KIND = "text";

export interface DefineEntityTypeSlideOverProps {
  open: boolean;
  onClose: () => void;
  editTarget: EntityType | null;
}

function cardinalityChangeMessage(from: EntityCardinality, to: EntityCardinality): string {
  // The operation looks instantaneous while the new representation stays empty until the
  // affected documents are re-extracted. Nothing is migrated and nothing is dropped, so this
  // dialog is the only thing standing between the admin and reading a successful save as
  // "the query surface now reflects this".
  if (from === "multi" && to === "single") {
    return (
      "Values already extracted for this entity type stay where they are — in its own table, " +
      "with every value per document. Switching to a single value does not move them. " +
      "Documents must be re-extracted before the single value is populated."
    );
  }
  return (
    "Values already extracted for this entity type stay where they are — one value per " +
    "document, on the document row. Switching to multiple values does not move them. " +
    "Documents must be re-extracted before the full set of values is populated."
  );
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
  const [cardinality, setCardinality] = useState<EntityCardinality>(DEFAULT_CARDINALITY);
  const [valueKind, setValueKind] = useState<string>(DEFAULT_VALUE_KIND);
  const [pendingConfirm, setPendingConfirm] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (editTarget) {
      setName(editTarget.name);
      setDescription(editTarget.description);
      setExamples(editTarget.examples.join(", "));
      const firstKey = Object.keys(editTarget.base_label_mapping)[0];
      setSelectedLabel(firstKey ?? BASE_LABELS[0]);
      setRequiredFlag(editTarget.required_flag);
      setCardinality(editTarget.cardinality ?? DEFAULT_CARDINALITY);
      setValueKind(editTarget.value_kind ?? DEFAULT_VALUE_KIND);
    } else {
      setName("");
      setDescription("");
      setExamples("");
      setSelectedLabel(BASE_LABELS[0]);
      setRequiredFlag(false);
      setCardinality(DEFAULT_CARDINALITY);
      setValueKind(DEFAULT_VALUE_KIND);
    }
    setPendingConfirm(false);
  }, [open, editTarget]);

  function buildPayload() {
    // Merged into the persisted mapping rather than replacing it. The chip row is a four-way
    // single select, so rebuilding the mapping from it drops every other key — and the
    // relational projection routes entities by the *full* key set, so a dropped key silently
    // empties part of a base-model tenant's query surface with no visible error.
    const entityName = name || editTarget?.name || "";
    const base_label_mapping = {
      ...(editTarget?.base_label_mapping ?? {}),
      [selectedLabel]: [entityName],
    };

    return {
      description,
      examples: examples
        .split(", ")
        .map((s) => s.trim())
        .filter(Boolean),
      base_label_mapping,
      required_flag: requiredFlag,
      cardinality,
      value_kind: valueKind,
    };
  }

  function sendUpdate() {
    if (!editTarget) return;
    updateMutation.mutate(
      { entityTypeName: editTarget.name, payload: buildPayload() },
      {
        onSuccess: () => {
          toast("Entity type updated successfully");
          setPendingConfirm(false);
          onClose();
        },
        onError: (err) => {
          setPendingConfirm(false);
          toast(err.message ?? "Update failed", "bad");
        },
      },
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (isEdit && editTarget) {
      // Create mode never prompts — there is nothing yet to be inconsistent with — and neither
      // does an edit that leaves cardinality alone.
      if (editTarget.cardinality !== cardinality) {
        setPendingConfirm(true);
        return;
      }
      sendUpdate();
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

          {/* CARDINALITY */}
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-secondary">
              Cardinality
            </label>
            <div className="flex gap-2">
              {CARDINALITY_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setCardinality(option.value)}
                  className={[
                    "flex-1 rounded px-3 py-2 text-left border transition-colors",
                    cardinality === option.value
                      ? "border-brand-primary bg-brand-primary text-white"
                      : "border-border hover:border-brand-primary hover:text-brand-primary",
                  ].join(" ")}
                  aria-pressed={cardinality === option.value}
                >
                  <span className="block text-xs font-medium">{option.label}</span>
                  <span className="block text-xs opacity-80">{option.hint}</span>
                </button>
              ))}
            </div>
          </div>

          {/* VALUE KIND */}
          <div>
            <label
              htmlFor="entity-value-kind"
              className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-secondary"
            >
              Value Kind
            </label>
            <select
              id="entity-value-kind"
              value={valueKind}
              onChange={(e) => setValueKind(e.target.value)}
              className="w-full rounded border border-border px-3 py-2 text-sm"
            >
              {VALUE_KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {kind}
                </option>
              ))}
            </select>
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

        {/* Cardinality change confirmation */}
        {pendingConfirm && editTarget && (
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Confirm cardinality change"
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 px-5"
          >
            <div className="w-full max-w-sm rounded-xl border border-border bg-surface-raised p-5 flex flex-col gap-3">
              <h3 className="text-sm font-semibold text-text-primary">
                {cardinality === "single"
                  ? "Change to a single value?"
                  : "Change to multiple values?"}
              </h3>
              <p className="text-xs text-text-secondary">
                {cardinalityChangeMessage(editTarget.cardinality, cardinality)}
              </p>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setPendingConfirm(false)}
                  className="rounded-lg border border-border px-4 py-2 text-sm font-semibold text-text-primary hover:bg-surface"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={sendUpdate}
                  disabled={isPending}
                  className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-hover disabled:opacity-50"
                >
                  Change cardinality
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </SlideOver>
  );
}
