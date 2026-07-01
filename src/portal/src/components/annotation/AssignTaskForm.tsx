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
  onAssign: (task: AnnotationTask) => void;
  onCancel: () => void;
}

export function AssignTaskForm({ onAssign, onCancel }: AssignTaskFormProps) {
  const { toast } = useToast();
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [selectedUserId, setSelectedUserId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);

  // Task 1.1 — fetch processed documents on-demand (enabled=true since form is already open)
  const { data: documentsData, isLoading: isLoadingDocuments } = useQuery({
    queryKey: ["assign-form-documents"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/documents?per_page=100&page=1");
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

  // Task 2.2 — filter client-side to processed only
  const processedDocuments = (documentsData ?? []).filter((d) => d.status === "processed");

  // Task 2.3 — filter client-side to annotator role only
  const annotatorUsers = (usersData ?? []).filter((u) => u.role === "annotator");

  const noAnnotators = !isLoadingUsers && annotatorUsers.length === 0;
  const noDocuments = !isLoadingDocuments && processedDocuments.length === 0;

  // Task 2.4 — Assign button disabled until both selected (and no empty results)
  const canSubmit = !!selectedDocumentId && !!selectedUserId && !isSubmitting;

  // Tasks 2.5-2.8 — submit handler
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setIsSubmitting(true);
    setInlineError(null);

    try {
      const res = await authFetch("/api/v1/annotation-tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_id: selectedDocumentId,
          annotator_user_id: selectedUserId,
        }),
      });

      if (res.status === 409) {
        // Task 2.7 — keep form open, show inline error
        setInlineError("This document already has an active task.");
        return;
      }

      if (!res.ok) {
        // Task 2.8 — generic error
        const err = await res.json().catch(() => ({}));
        setInlineError(
          (err as { detail?: string }).detail ?? "Failed to create task. Please try again."
        );
        return;
      }

      // Task 2.6 — success
      const newTask = await res.json();
      toast("Task assigned successfully", "good");
      onAssign(newTask as AnnotationTask);
    } catch {
      setInlineError("Network error. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
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
      {/* Document dropdown */}
      <div>
        <label style={labelStyle}>Document</label>
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
          <select
            data-testid="document-select"
            value={selectedDocumentId}
            onChange={(e) => { setSelectedDocumentId(e.target.value); setInlineError(null); }}
            style={selectStyle}
          >
            <option value="">Select a document…</option>
            {processedDocuments.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename}
              </option>
            ))}
          </select>
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

      {/* Inline error */}
      {inlineError && (
        <div
          data-testid="assign-form-error"
          style={{ fontSize: 12, color: "var(--color-error, #ef4444)" }}
        >
          {inlineError}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
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
          {isSubmitting ? "Assigning…" : "Assign"}
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
      </div>
    </form>
  );
}
