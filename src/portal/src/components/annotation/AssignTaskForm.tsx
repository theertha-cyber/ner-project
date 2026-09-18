"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import { useToast } from "@/hooks/use-toast";
import type { AnnotationTask } from "./TaskQueue";
import type { Document } from "@/types/documents";

interface User {
  id: string;
  email: string;
  role: string;
  status: string;
}

interface AssignTaskFormProps {
  onAssign: (tasks: AnnotationTask[]) => void;
  onCancel: () => void;
}

/** Per-document outcome of a submitted batch, keyed by document_id. */
type AssignOutcome =
  | { status: "success"; task: AnnotationTask }
  | { status: "conflict"; message: string }
  | { status: "error"; message: string };

export function AssignTaskForm({ onAssign, onCancel }: AssignTaskFormProps) {
  const { toast } = useToast();
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<Set<string>>(new Set());
  const [selectedUserId, setSelectedUserId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);
  // Set only once a submitted batch included at least one failure — the success case closes
  // the form immediately instead, matching the single-document flow's prior behavior.
  const [results, setResults] = useState<Record<string, AssignOutcome> | null>(null);

  // Task 1.1 — fetch processed documents on-demand (enabled=true since form is already open)
  const { data: documentsData, isLoading: isLoadingDocuments } = useQuery({
    queryKey: ["assign-form-documents"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/documents?purpose=training&per_page=100&page=1");
      if (!res.ok) throw new Error("Failed to load documents");
      const data = await res.json();
      return (data.documents ?? []) as Document[];
    },
  });

  // Task 1.2 — fetch annotator users on-demand
  const { data: usersData, isLoading: isLoadingUsers } = useQuery({
    queryKey: ["assign-form-users"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/users");
      if (!res.ok) throw new Error("Failed to load users");
      const data = await res.json();
      return (data.users ?? data) as User[];
    },
  });

  // Fetch existing tasks so documents with an active (non-completed) task
  // are excluded from the list — prevents assigning the same document twice.
  const { data: tasksData } = useQuery({
    queryKey: ["assign-form-active-tasks"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/annotation-tasks");
      if (!res.ok) throw new Error("Failed to load tasks");
      const data = await res.json();
      return (Array.isArray(data) ? data : []) as AnnotationTask[];
    },
  });

  const documentIdsWithActiveTask = new Set(
    (tasksData ?? [])
      .filter((t) => t.status === "unannotated" || t.status === "in-progress")
      .map((t) => t.document_id)
  );

  // Task 2.2 — filter client-side to processed only, excluding docs already assigned
  const processedDocuments = (documentsData ?? []).filter(
    (d) => d.status === "processed" && !documentIdsWithActiveTask.has(d.id)
  );

  // Task 2.3 — filter client-side to annotator role only
  const annotatorUsers = (usersData ?? []).filter((u) => u.role === "annotator");

  const noAnnotators = !isLoadingUsers && annotatorUsers.length === 0;
  const noDocuments = !isLoadingDocuments && processedDocuments.length === 0;

  const toggleDocument = (docId: string) => {
    setInlineError(null);
    setSelectedDocumentIds((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  };

  const selectAll = () => setSelectedDocumentIds(new Set(processedDocuments.map((d) => d.id)));
  const clearAll = () => setSelectedDocumentIds(new Set());

  const canSubmit = selectedDocumentIds.size > 0 && !!selectedUserId && !isSubmitting;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setIsSubmitting(true);
    setInlineError(null);
    setResults(null);

    const documentIds = Array.from(selectedDocumentIds);
    const outcomes: Record<string, AssignOutcome> = {};

    // Sequential, not parallel: each POST is checked against the same "one active task per
    // document" conflict rule, and the annotation service has no bulk endpoint for this — one
    // request per document, same as the batch document uploader's own pattern.
    for (const documentId of documentIds) {
      try {
        const res = await authFetch("/api/v1/annotation-tasks", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            document_id: documentId,
            annotator_user_id: selectedUserId,
          }),
        });

        if (res.status === 409) {
          outcomes[documentId] = { status: "conflict", message: "Already has an active task" };
          continue;
        }
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          outcomes[documentId] = {
            status: "error",
            message: (err as { detail?: string }).detail ?? "Failed to assign",
          };
          continue;
        }
        const newTask = (await res.json()) as AnnotationTask;
        outcomes[documentId] = { status: "success", task: newTask };
      } catch {
        outcomes[documentId] = { status: "error", message: "Network error" };
      }
    }

    setIsSubmitting(false);

    const createdTasks = Object.values(outcomes)
      .filter((o): o is Extract<AssignOutcome, { status: "success" }> => o.status === "success")
      .map((o) => o.task);
    const failureCount = documentIds.length - createdTasks.length;

    if (failureCount === 0) {
      // Every document assigned cleanly — close immediately, matching the prior
      // single-document flow's behavior. Nothing here needs a second look.
      toast(
        createdTasks.length === 1
          ? "Task assigned successfully"
          : `${createdTasks.length} tasks assigned successfully`,
        "ok",
      );
      onAssign(createdTasks);
      return;
    }

    // At least one document failed — keep the form open and show exactly which ones, rather
    // than silently dropping them or closing over an error the admin hasn't seen yet.
    setResults(outcomes);
    if (createdTasks.length > 0) {
      toast(`${createdTasks.length} of ${documentIds.length} tasks assigned`, "ok");
    } else {
      toast("No tasks could be assigned", "bad");
    }
  };

  const handleDone = () => {
    if (!results) return;
    const createdTasks = Object.values(results)
      .filter((o): o is Extract<AssignOutcome, { status: "success" }> => o.status === "success")
      .map((o) => o.task);
    onAssign(createdTasks);
  };

  const labelStyle: React.CSSProperties = {
    display: "block",
    fontSize: 11,
    fontWeight: 600,
    color: "var(--color-text-secondary)",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    marginBottom: 4,
  };

  const selectStyle: React.CSSProperties = {
    width: "100%",
    fontSize: 12,
    padding: "5px 8px",
    borderRadius: 5,
    border: "1px solid var(--color-border, var(--line))",
    background: "var(--surface-1, var(--color-bg))",
    color: "var(--color-text-primary)",
    cursor: "pointer",
  };

  const selectedCount = selectedDocumentIds.size;

  return (
    <form
      onSubmit={handleSubmit}
      data-testid="assign-task-form"
      style={{
        padding: "10px 12px",
        borderBottom: "1px solid var(--color-border)",
        background: "var(--color-primary-soft, rgba(99,102,241,0.06))",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      {/* Document multi-select */}
      <div>
        <label style={labelStyle}>
          Documents{selectedCount > 0 ? ` (${selectedCount} selected)` : ""}
        </label>
        {isLoadingDocuments ? (
          <div style={{ fontSize: 12, color: "var(--color-text-secondary)", padding: "4px 0" }}>
            Loading…
          </div>
        ) : noDocuments ? (
          <div
            data-testid="no-documents-message"
            style={{ fontSize: 12, color: "var(--color-text-secondary)", padding: "4px 0" }}
          >
            No processed documents available
          </div>
        ) : (
          <>
            <div style={{ display: "flex", gap: 10, marginBottom: 4 }}>
              <button
                type="button"
                data-testid="select-all-documents-btn"
                onClick={selectAll}
                style={{ fontSize: 11, background: "none", border: "none", color: "var(--color-primary, #6366f1)", cursor: "pointer", padding: 0 }}
              >
                Select all ({processedDocuments.length})
              </button>
              {selectedCount > 0 && (
                <button
                  type="button"
                  data-testid="clear-documents-btn"
                  onClick={clearAll}
                  style={{ fontSize: 11, background: "none", border: "none", color: "var(--color-text-secondary)", cursor: "pointer", padding: 0 }}
                >
                  Clear
                </button>
              )}
            </div>
            <div
              data-testid="document-checkbox-list"
              style={{
                maxHeight: 160,
                overflowY: "auto",
                border: "1px solid var(--color-border, var(--line))",
                borderRadius: 5,
                background: "var(--surface-1, var(--color-bg))",
              }}
            >
              {processedDocuments.map((doc) => (
                <label
                  key={doc.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "5px 8px",
                    fontSize: 12,
                    color: "var(--color-text-primary)",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    data-testid={`document-checkbox-${doc.id}`}
                    checked={selectedDocumentIds.has(doc.id)}
                    onChange={() => toggleDocument(doc.id)}
                  />
                  {doc.filename}
                </label>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Annotator dropdown */}
      <div>
        <label style={labelStyle}>Annotator</label>
        {isLoadingUsers ? (
          <div style={{ fontSize: 12, color: "var(--color-text-secondary)", padding: "4px 0" }}>
            Loading…
          </div>
        ) : noAnnotators ? (
          <div
            data-testid="no-annotators-message"
            style={{ fontSize: 12, color: "var(--color-text-secondary)", padding: "4px 0" }}
          >
            No annotators available — invite users first
          </div>
        ) : (
          <select
            data-testid="annotator-select"
            value={selectedUserId}
            onChange={(e) => { setSelectedUserId(e.target.value); setInlineError(null); }}
            style={selectStyle}
          >
            <option value="">Select an annotator…</option>
            {annotatorUsers.map((u) => (
              <option key={u.id} value={u.id}>
                {u.email}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Inline error (pre-submit validation only — per-document outcomes render below) */}
      {inlineError && (
        <div
          data-testid="assign-form-error"
          style={{ fontSize: 12, color: "var(--color-error, #ef4444)" }}
        >
          {inlineError}
        </div>
      )}

      {/* Per-document results, shown only when at least one document in the batch failed */}
      {results && (
        <div data-testid="assign-results" style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {Object.entries(results).map(([docId, outcome]) => {
            const doc = processedDocuments.find((d) => d.id === docId);
            return (
              <div
                key={docId}
                data-testid={`assign-result-${docId}`}
                style={{
                  fontSize: 11.5,
                  color: outcome.status === "success" ? "var(--good, #16a34a)" : "var(--color-error, #ef4444)",
                }}
              >
                {outcome.status === "success"
                  ? `✓ ${doc?.filename ?? docId} assigned`
                  : `✕ ${doc?.filename ?? docId}: ${outcome.message}`}
              </div>
            );
          })}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {results ? (
          <button
            type="button"
            data-testid="assign-done-btn"
            onClick={handleDone}
            style={{
              padding: "5px 12px",
              fontSize: 12,
              fontWeight: 600,
              borderRadius: 5,
              border: "none",
              background: "var(--color-primary, #6366f1)",
              color: "#fff",
              cursor: "pointer",
            }}
          >
            Done
          </button>
        ) : (
          <>
            <button
              type="submit"
              data-testid="assign-submit-btn"
              disabled={!canSubmit || noAnnotators || noDocuments}
              style={{
                padding: "5px 12px",
                fontSize: 12,
                fontWeight: 600,
                borderRadius: 5,
                border: "none",
                background: canSubmit && !noAnnotators && !noDocuments
                  ? "var(--color-primary, #6366f1)"
                  : "var(--color-border)",
                color: canSubmit && !noAnnotators && !noDocuments ? "#fff" : "var(--color-text-secondary)",
                cursor: canSubmit && !noAnnotators && !noDocuments ? "pointer" : "not-allowed",
                opacity: isSubmitting ? 0.7 : 1,
              }}
            >
              {isSubmitting
                ? "Assigning…"
                : selectedCount > 1
                  ? `Assign ${selectedCount} documents`
                  : "Assign"}
            </button>
            <button
              type="button"
              data-testid="assign-cancel-btn"
              onClick={onCancel}
              style={{
                fontSize: 12,
                background: "none",
                border: "none",
                color: "var(--color-text-secondary)",
                cursor: "pointer",
                padding: "5px 4px",
              }}
            >
              Cancel
            </button>
          </>
        )}
      </div>
    </form>
  );
}
