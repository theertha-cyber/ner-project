"use client";

import { useReducer, useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { authFetch } from "@/lib/auth-fetch";
import { useToast } from "@/hooks/use-toast";
import { buildTokenMap } from "@/lib/token-map";
import { spanReducer, initialSpanState } from "./span-reducer";
import type { ConfirmedSpan } from "./span-reducer";
import { TaskQueue, AnnotationTask } from "./TaskQueue";
import { DocumentViewer } from "./DocumentViewer";
import { EntityPalette, EntityTypeItem } from "./EntityPalette";
import { SpanInspector } from "./SpanInspector";
import { SuggestionPanel } from "./SuggestionPanel";

type LayoutMode = "3pane" | "focus";

const LAYOUT_KEY = "ner-annotation-layout";

const ENTITY_COLORS = [
  "#6366f1", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6",
  "#3b82f6", "#f97316", "#ec4899", "#14b8a6", "#84cc16",
];

function buildEntityColors(entityTypes: EntityTypeItem[]): Record<string, string> {
  const colors: Record<string, string> = {};
  entityTypes.forEach((et, i) => {
    colors[et.name] = ENTITY_COLORS[i % ENTITY_COLORS.length];
  });
  return colors;
}

export function AnnotationPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [spanState, dispatch] = useReducer(spanReducer, initialSpanState);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("3pane");
  const [selectedTask, setSelectedTask] = useState<AnnotationTask | null>(null);
  const [docText, setDocText] = useState<string | null>(null);
  const [taskStatuses, setTaskStatuses] = useState<Record<string, AnnotationTask["status"]>>({});
  const [isPrelabeling, setIsPrelabeling] = useState(false);
  const sentInProgressRef = useRef<Set<string>>(new Set());
  const [isDragging, setIsDragging] = useState(false);
  const [dragStartIndex, setDragStartIndex] = useState<number | null>(null);
  const [dragEndIndex, setDragEndIndex] = useState<number | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem(LAYOUT_KEY);
    if (saved === "3pane" || saved === "focus") setLayoutMode(saved);
  }, []);

  // Global Escape key handler
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") dispatch({ type: "DISARM" });
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  const { data: tasksData } = useQuery({
    queryKey: ["annotation-tasks"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/annotation-tasks");
      if (!res.ok) throw new Error("Failed to load tasks");
      return res.json() as Promise<AnnotationTask[]>;
    },
  });

  const { data: entityTypesData } = useQuery({
    queryKey: ["entity-types"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/entity-types");
      if (!res.ok) throw new Error("Failed to load entity types");
      const data = await res.json();
      return (data.entity_types ?? []) as EntityTypeItem[];
    },
  });

  const allTasks: AnnotationTask[] = tasksData ?? [];
  const entityTypes: EntityTypeItem[] = entityTypesData ?? [];

  const filteredTasks = useMemo(() => {
    if (!user) return allTasks;
    if (user.role === "annotator") {
      return allTasks.filter((t) => t.annotator_user_id === user.userId);
    }
    return allTasks;
  }, [allTasks, user]);

  const entityColors = useMemo(() => buildEntityColors(entityTypes), [entityTypes]);

  const tokenMap = useMemo(
    () => (docText ? buildTokenMap(docText) : []),
    [docText],
  );

  const handleSelectTask = useCallback(
    async (task: AnnotationTask) => {
      setSelectedTask(task);
      setDocText(null);
      dispatch({ type: "SPANS_LOAD", spans: [] });
      dispatch({ type: "SUGGESTIONS_LOAD", spans: [] });
      dispatch({ type: "DISARM" });

      try {
        const [textRes, spansRes, suggestedRes] = await Promise.all([
          authFetch(`/api/v1/documents/${task.document_id}/text`),
          authFetch(`/api/v1/documents/${task.document_id}/spans`),
          authFetch(`/api/v1/documents/${task.document_id}/spans?type=suggested`),
        ]);

        if (textRes.ok) {
          const { text } = await textRes.json();
          setDocText(text);
        }

        if (spansRes.ok) {
          const spans: ConfirmedSpan[] = ((await spansRes.json()) as Array<{
            id: string; entity_type: string; char_start: number; char_end: number; text: string; confidence: number;
          }>).map((s) => ({
            id: s.id,
            entityType: s.entity_type,
            charStart: s.char_start,
            charEnd: s.char_end,
            text: s.text,
            confidence: s.confidence,
          }));
          dispatch({ type: "SPANS_LOAD", spans });
        }

        if (suggestedRes.ok) {
          const suggested = ((await suggestedRes.json()) as Array<{
            id: string; entity_type: string; char_start: number; char_end: number; text: string; confidence: number;
          }>).map((s) => ({
            id: s.id,
            entityType: s.entity_type,
            charStart: s.char_start,
            charEnd: s.char_end,
            text: s.text,
            confidence: s.confidence,
          }));
          dispatch({ type: "SUGGESTIONS_LOAD", spans: suggested });
        }
      } catch {
        toast("Failed to load document", "bad");
      }
    },
    [toast],
  );

  const handleTokenClick = useCallback(
    async (tokenIndex: number) => {
      if (!selectedTask || !docText) return;
      const entry = tokenMap[tokenIndex];
      if (!entry) return;

      if (spanState.armedType) {
        // Check if token already covered by a confirmed span
        const alreadyCovered = spanState.confirmed.some(
          (s) => !s.optimistic && s.charStart <= entry.charStart && s.charEnd >= entry.charEnd,
        );
        if (alreadyCovered) return;

        const optimisticId = `optimistic-${crypto.randomUUID()}`;
        const optimisticSpan: ConfirmedSpan = {
          id: optimisticId,
          entityType: spanState.armedType,
          charStart: entry.charStart,
          charEnd: entry.charEnd,
          text: entry.token,
          confidence: 1.0,
          optimistic: true,
        };
        dispatch({ type: "SPAN_ADD_OPTIMISTIC", span: optimisticSpan });

        try {
          const res = await authFetch(`/api/v1/documents/${selectedTask.document_id}/spans`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              entity_type: spanState.armedType,
              char_start: entry.charStart,
              char_end: entry.charEnd,
              text: entry.token,
            }),
          });

          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            dispatch({ type: "SPAN_REVERT", optimisticId });
            toast((err as { error?: { message?: string } }).error?.message ?? "Failed to create span", "bad");
            return;
          }

          const data = await res.json();
          const realSpan: ConfirmedSpan = {
            id: data.id,
            entityType: data.entity_type,
            charStart: data.char_start,
            charEnd: data.char_end,
            text: data.text,
            confidence: data.confidence,
          };
          dispatch({ type: "SPAN_CONFIRM", optimisticId, realSpan });

          // Transition unannotated → in-progress on first span
          const currentStatus = taskStatuses[selectedTask.id] ?? selectedTask.status;
          if (currentStatus === "unannotated" && !sentInProgressRef.current.has(selectedTask.id)) {
            sentInProgressRef.current.add(selectedTask.id);
            const patchRes = await authFetch(`/api/v1/annotation-tasks/${selectedTask.id}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ status: "in-progress" }),
            });
            if (patchRes.ok) {
              setTaskStatuses((prev) => ({ ...prev, [selectedTask.id]: "in-progress" }));
            }
          }
        } catch {
          dispatch({ type: "SPAN_REVERT", optimisticId });
          toast("Failed to create span", "bad");
        }
      } else {
        // No armed type — open inspector for confirmed span at this token, or deselect
        const confirmedAtToken = spanState.confirmed.find(
          (s) => !s.optimistic && s.charStart <= entry.charStart && s.charEnd >= entry.charEnd,
        );
        if (confirmedAtToken) {
          dispatch({ type: "SPAN_SET_SELECTED", spanId: confirmedAtToken.id });
        } else {
          dispatch({ type: "SPAN_SET_SELECTED", spanId: null });
        }
      }
    },
    [selectedTask, docText, tokenMap, spanState.armedType, spanState.confirmed, taskStatuses, toast],
  );

  // Document-level mouseup handler for drag span creation (placed after tokenMap + handleTokenClick)
  useEffect(() => {
    const handler = async () => {
      if (!isDragging || dragStartIndex === null) {
        setIsDragging(false);
        setDragStartIndex(null);
        setDragEndIndex(null);
        return;
      }

      const startIdx = dragStartIndex;
      const endIdx = dragEndIndex ?? dragStartIndex;
      const minIdx = Math.min(startIdx, endIdx);
      const maxIdx = Math.max(startIdx, endIdx);

      setIsDragging(false);
      setDragStartIndex(null);
      setDragEndIndex(null);

      // Single-click (same token): fall through to handleTokenClick
      if (minIdx === maxIdx) {
        handleTokenClick(minIdx);
        return;
      }

      if (!spanState.armedType || !selectedTask || !docText) return;

      // Guard: cancel if any token in range is already confirmed
      const rangeEntries = tokenMap.slice(minIdx, maxIdx + 1);
      const blocked = rangeEntries.some((entry) =>
        spanState.confirmed.some(
          (s) => !s.optimistic && s.charStart <= entry.charStart && s.charEnd >= entry.charEnd,
        ),
      );
      if (blocked) return;

      const charStart = tokenMap[minIdx].charStart;
      const charEnd = tokenMap[maxIdx].charEnd;
      const spanText = docText.slice(charStart, charEnd);

      const optimisticId = `optimistic-${crypto.randomUUID()}`;
      const optimisticSpan: ConfirmedSpan = {
        id: optimisticId,
        entityType: spanState.armedType,
        charStart,
        charEnd,
        text: spanText,
        confidence: 1.0,
        optimistic: true,
      };
      dispatch({ type: "SPAN_ADD_OPTIMISTIC", span: optimisticSpan });

      try {
        const res = await authFetch(`/api/v1/documents/${selectedTask.document_id}/spans`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            entity_type: spanState.armedType,
            char_start: charStart,
            char_end: charEnd,
            text: spanText,
          }),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          dispatch({ type: "SPAN_REVERT", optimisticId });
          toast((err as { error?: { message?: string } }).error?.message ?? "Failed to create span", "bad");
          return;
        }

        const data = await res.json();
        const realSpan: ConfirmedSpan = {
          id: data.id,
          entityType: data.entity_type,
          charStart: data.char_start,
          charEnd: data.char_end,
          text: data.text,
          confidence: data.confidence,
        };
        dispatch({ type: "SPAN_CONFIRM", optimisticId, realSpan });

        const currentStatus = taskStatuses[selectedTask.id] ?? selectedTask.status;
        if (currentStatus === "unannotated" && !sentInProgressRef.current.has(selectedTask.id)) {
          sentInProgressRef.current.add(selectedTask.id);
          const patchRes = await authFetch(`/api/v1/annotation-tasks/${selectedTask.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "in-progress" }),
          });
          if (patchRes.ok) {
            setTaskStatuses((prev) => ({ ...prev, [selectedTask.id]: "in-progress" }));
          }
        }
      } catch {
        dispatch({ type: "SPAN_REVERT", optimisticId });
        toast("Failed to create span", "bad");
      }
    };

    document.addEventListener("mouseup", handler);
    return () => document.removeEventListener("mouseup", handler);
  }, [isDragging, dragStartIndex, dragEndIndex, spanState.armedType, spanState.confirmed, selectedTask, docText, tokenMap, taskStatuses, toast, handleTokenClick]);

  const handleTokenMouseDown = useCallback((tokenIndex: number) => {
    setIsDragging(true);
    setDragStartIndex(tokenIndex);
    setDragEndIndex(tokenIndex);
  }, []);

  const handleTokenMouseEnter = useCallback((tokenIndex: number) => {
    if (isDragging) {
      setDragEndIndex(tokenIndex);
    }
  }, [isDragging]);

  const handleRetype = useCallback(
    async (spanId: string, entityType: string) => {
      if (!selectedTask) return;
      dispatch({ type: "SPAN_RETYPE", spanId, entityType });
      const res = await authFetch(
        `/api/v1/documents/${selectedTask.document_id}/spans/${spanId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ entity_type: entityType }),
        },
      );
      if (!res.ok) {
        toast("Failed to update span", "bad");
      }
    },
    [selectedTask, toast],
  );

  const handleDelete = useCallback(
    async (spanId: string) => {
      if (!selectedTask) return;
      dispatch({ type: "SPAN_DELETE", spanId });
      const res = await authFetch(
        `/api/v1/documents/${selectedTask.document_id}/spans/${spanId}`,
        { method: "DELETE" },
      );
      if (!res.ok) {
        toast("Failed to delete span", "bad");
      }
    },
    [selectedTask, toast],
  );

  const handlePrelabel = useCallback(async () => {
    if (!selectedTask || isPrelabeling) return;
    setIsPrelabeling(true);
    try {
      const res = await authFetch(
        `/api/v1/documents/${selectedTask.document_id}/prelabel`,
        { method: "POST" },
      );
      if (!res.ok) {
        toast("Pre-labeling failed", "bad");
        return;
      }
      const data = await res.json();
      const suggested = ((data as Array<{
        id: string; entity_type: string; char_start: number; char_end: number; text: string; confidence: number;
      }>)).map((s) => ({
        id: s.id,
        entityType: s.entity_type,
        charStart: s.char_start,
        charEnd: s.char_end,
        text: s.text,
        confidence: s.confidence,
      }));
      dispatch({ type: "SUGGESTIONS_LOAD", spans: suggested });
    } catch {
      toast("Pre-labeling failed", "bad");
    } finally {
      setIsPrelabeling(false);
    }
  }, [selectedTask, isPrelabeling, toast]);

  const handlePromote = useCallback(
    async (suggestId: string) => {
      if (!selectedTask) return;
      const suggestion = spanState.suggested.find((s) => s.id === suggestId);
      if (!suggestion) return;

      const res = await authFetch(
        `/api/v1/documents/${selectedTask.document_id}/spans/promote/${suggestId}`,
        { method: "POST" },
      );
      if (!res.ok) {
        toast("Failed to promote suggestion", "bad");
        return;
      }
      const data = await res.json();
      const confirmedSpan: ConfirmedSpan = {
        id: data.id,
        entityType: data.entity_type,
        charStart: data.char_start,
        charEnd: data.char_end,
        text: data.text,
        confidence: data.confidence,
      };
      dispatch({ type: "SUGGESTION_PROMOTE", suggestId, confirmedSpan });

      const currentStatus = taskStatuses[selectedTask.id] ?? selectedTask.status;
      if (currentStatus === "unannotated" && !sentInProgressRef.current.has(selectedTask.id)) {
        sentInProgressRef.current.add(selectedTask.id);
        const patchRes = await authFetch(`/api/v1/annotation-tasks/${selectedTask.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "in-progress" }),
        });
        if (patchRes.ok) {
          setTaskStatuses((prev) => ({ ...prev, [selectedTask.id]: "in-progress" }));
        }
      }
    },
    [selectedTask, spanState.suggested, taskStatuses, toast],
  );

  const handleDismiss = useCallback((suggestId: string) => {
    dispatch({ type: "SUGGESTION_DISMISS", suggestId });
  }, []);

  const handleMarkComplete = useCallback(async () => {
    if (!selectedTask) return;
    const res = await authFetch(`/api/v1/annotation-tasks/${selectedTask.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "completed" }),
    });
    if (!res.ok) {
      toast("Failed to complete task", "bad");
      return;
    }
    setTaskStatuses((prev) => ({ ...prev, [selectedTask.id]: "completed" }));
    // Auto-select next non-completed task
    const nextTask = filteredTasks.find((t) => {
      const status = taskStatuses[t.id] ?? t.status;
      return t.id !== selectedTask.id && status !== "completed";
    });
    if (nextTask) handleSelectTask(nextTask);
  }, [selectedTask, filteredTasks, taskStatuses, toast, handleSelectTask]);

  const selectedSpan = spanState.selectedSpanId
    ? spanState.confirmed.find((s) => s.id === spanState.selectedSpanId) ?? null
    : null;

  const confirmedCount = spanState.confirmed.filter((s) => !s.optimistic).length;
  const currentTaskStatus = selectedTask
    ? (taskStatuses[selectedTask.id] ?? selectedTask.status)
    : null;

  // Sync layout state when browser exits fullscreen via Escape or native controls
  useEffect(() => {
    const handler = () => {
      if (!document.fullscreenElement) {
        setLayoutMode("3pane");
        localStorage.setItem(LAYOUT_KEY, "3pane");
      }
    };
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  const toggleLayout = (mode: LayoutMode) => {
    setLayoutMode(mode);
    localStorage.setItem(LAYOUT_KEY, mode);
    if (mode === "focus") {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  return (
    <div style={{ display: "flex", height: "100%", minHeight: 0, position: "relative" }}>
      {/* Task Queue — hidden in focus mode */}
      {layoutMode === "3pane" && (
        <div
          style={{
            width: 220,
            flexShrink: 0,
            borderRight: "1px solid var(--color-border)",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              padding: "12px 12px 8px",
              fontSize: 11,
              fontWeight: 600,
              color: "var(--color-text-secondary)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              borderBottom: "1px solid var(--color-border)",
            }}
          >
            Task Queue
          </div>
          <div style={{ padding: "8px 6px", flex: 1, overflowY: "auto" }}>
            <TaskQueue
              tasks={filteredTasks}
              selectedTaskId={selectedTask?.id ?? null}
              taskStatuses={taskStatuses}
              onSelect={handleSelectTask}
            />
          </div>
        </div>
      )}

      {/* Center: Document Viewer */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Toolbar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "10px 16px",
            borderBottom: "1px solid var(--color-border)",
            flexShrink: 0,
          }}
        >
          {/* Layout toggle */}
          <button
            onClick={() => toggleLayout(layoutMode === "focus" ? "3pane" : "focus")}
            style={{
              padding: "3px 10px",
              borderRadius: 6,
              border: layoutMode === "focus" ? "none" : "1px solid var(--color-border)",
              background: layoutMode === "focus" ? "var(--color-brand-primary)" : "transparent",
              color: layoutMode === "focus" ? "#fff" : "var(--color-text-secondary)",
              fontSize: 12,
              cursor: "pointer",
              fontWeight: layoutMode === "focus" ? 600 : 400,
              transition: "all 0.15s",
            }}
          >
            Focus
          </button>

          {selectedTask && (
            <>
              <span style={{ fontSize: 12, color: "var(--color-text-secondary)", marginLeft: 4 }}>
                Task {filteredTasks.indexOf(selectedTask) + 1}
              </span>
              <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
                <button
                  onClick={handlePrelabel}
                  disabled={isPrelabeling}
                  style={{
                    padding: "5px 12px",
                    borderRadius: 6,
                    border: "1px solid var(--color-border)",
                    background: "var(--color-surface-raised)",
                    color: isPrelabeling ? "var(--color-text-secondary)" : "var(--color-text-primary)",
                    fontSize: 12,
                    cursor: isPrelabeling ? "not-allowed" : "pointer",
                    opacity: isPrelabeling ? 0.6 : 1,
                  }}
                >
                  {isPrelabeling ? "Pre-labeling…" : "Pre-label"}
                </button>
                <button
                  onClick={handleMarkComplete}
                  disabled={confirmedCount === 0 || currentTaskStatus === "completed"}
                  title={
                    currentTaskStatus === "completed"
                      ? "Task already completed"
                      : confirmedCount === 0
                      ? "Add at least one confirmed span before completing"
                      : undefined
                  }
                  style={{
                    padding: "5px 12px",
                    borderRadius: 6,
                    border: (confirmedCount === 0 || currentTaskStatus === "completed") ? "1px solid var(--color-border)" : "none",
                    background: (confirmedCount === 0 || currentTaskStatus === "completed") ? "transparent" : "var(--color-brand-primary)",
                    color: (confirmedCount === 0 || currentTaskStatus === "completed") ? "var(--color-text-secondary)" : "#fff",
                    fontSize: 12,
                    cursor: (confirmedCount === 0 || currentTaskStatus === "completed") ? "not-allowed" : "pointer",
                    fontWeight: 500,
                  }}
                >
                  Mark Complete
                </button>
              </div>
            </>
          )}
        </div>

        {/* Armed-mode banner */}
        {spanState.armedType && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 16px",
              background: (entityColors[spanState.armedType] ?? "#6366f1") + "22",
              borderBottom: "1px solid " + (entityColors[spanState.armedType] ?? "#6366f1") + "44",
              flexShrink: 0,
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: entityColors[spanState.armedType] ?? "#6366f1",
                display: "inline-block",
                flexShrink: 0,
              }}
            />
            <span style={{ fontSize: 13, color: "var(--color-text-primary)", fontWeight: 500 }}>
              Labeling as <strong>{spanState.armedType}</strong> — click any word to create a span
            </span>
            <button
              onClick={() => dispatch({ type: "DISARM" })}
              style={{
                marginLeft: "auto",
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "var(--color-text-secondary)",
                fontSize: 13,
              }}
            >
              × Disarm
            </button>
          </div>
        )}

        {/* Document text */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "16px 20px",
            position: "relative",
          }}
        >
          <DocumentViewer
            tokenMap={tokenMap}
            spanState={spanState}
            entityColors={entityColors}
            onTokenClick={handleTokenClick}
            onTokenMouseDown={handleTokenMouseDown}
            onTokenMouseEnter={handleTokenMouseEnter}
            isDragging={isDragging}
            dragStartIndex={dragStartIndex}
            dragEndIndex={dragEndIndex}
          />

          {/* Span Inspector (positioned inside the scrollable area) */}
          {selectedSpan && (
            <SpanInspector
              span={selectedSpan}
              entityTypes={entityTypes}
              onRetype={handleRetype}
              onDelete={handleDelete}
              onClose={() => dispatch({ type: "SPAN_SET_SELECTED", spanId: null })}
            />
          )}
        </div>

        {/* Suggestions panel */}
        {spanState.suggested.length > 0 && selectedTask && (
          <div
            style={{
              borderTop: "1px solid var(--color-border)",
              padding: "12px 16px",
              maxHeight: 200,
              overflowY: "auto",
              flexShrink: 0,
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "var(--color-text-secondary)",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: 8,
              }}
            >
              Suggestions ({spanState.suggested.length})
            </div>
            <SuggestionPanel
              suggestions={spanState.suggested}
              entityColors={entityColors}
              onPromote={handlePromote}
              onDismiss={handleDismiss}
            />
          </div>
        )}
      </div>

      {/* Entity Palette — right column in 3pane, fixed in focus */}
      <div
        style={
          layoutMode === "focus"
            ? {
                position: "fixed",
                top: 140,
                right: 30,
                width: 200,
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 10,
                boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
                padding: "12px",
                zIndex: 30,
                maxHeight: "60vh",
                overflowY: "auto",
              }
            : {
                width: 200,
                flexShrink: 0,
                borderLeft: "1px solid var(--color-border)",
                padding: "12px",
                overflowY: "auto",
              }
        }
      >
        <EntityPalette
          entityTypes={entityTypes}
          entityColors={entityColors}
          confirmedSpans={spanState.confirmed}
          armedType={spanState.armedType}
          onArm={(name) => dispatch({ type: "ARM", entityType: name })}
          onDisarm={() => dispatch({ type: "DISARM" })}
        />
      </div>
    </div>
  );
}
