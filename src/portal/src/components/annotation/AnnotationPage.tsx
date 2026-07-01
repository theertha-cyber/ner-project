"use client";

import { useReducer, useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
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
import { AnnotationToolbar } from "./AnnotationToolbar";
import { ArmedBanner } from "./ArmedBanner";
import { FocusPalette } from "./FocusPalette";
import { AssignTaskForm } from "./AssignTaskForm";

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
  const queryClient = useQueryClient();
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
  // Task 3.1 — admin-only assign form state
  const isAdmin = user?.role === "tenant_admin";
  const [isAssignFormOpen, setIsAssignFormOpen] = useState(false);

  // Restore layout from localStorage on mount (CSS-only — no fullscreen)
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
    queryKey: ["entity-types", user?.tenantSlug],
    enabled: !!user?.tenantSlug,
    queryFn: async () => {
      const res = await authFetch(`/api/v1/tenants/${user!.tenantSlug}/entity-types`);
      if (!res.ok) throw new Error("Failed to load entity types");
      const data = await res.json();
      return (data.entity_types ?? []) as EntityTypeItem[];
    },
  });

  const [locallyPrependedTasks, setLocallyPrependedTasks] = useState<AnnotationTask[]>([]);
  const allTasks: AnnotationTask[] = [...locallyPrependedTasks, ...(tasksData ?? [])];
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

  const handleLayoutChange = useCallback((mode: LayoutMode) => {
    setLayoutMode(mode);
    localStorage.setItem(LAYOUT_KEY, mode);
    // CSS-only focus mode — no fullscreen API
  }, []);

  // Task 3.4 — prepend new task from assignment form and close it
  const handleTaskAssigned = useCallback((newTask: AnnotationTask) => {
    setLocallyPrependedTasks((prev) => [newTask, ...prev]);
    setIsAssignFormOpen(false);
    queryClient.invalidateQueries({ queryKey: ["annotation-tasks"] });
  }, [queryClient]);

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

  const handleStatusChange = useCallback(
    (newStatus: AnnotationTask["status"]) => {
      if (!selectedTask) return;
      setTaskStatuses((prev) => ({ ...prev, [selectedTask.id]: newStatus }));
    },
    [selectedTask],
  );

  const handleTokenClick = useCallback(
    async (tokenIndex: number) => {
      if (!selectedTask || !docText) return;
      const entry = tokenMap[tokenIndex];
      if (!entry) return;

      if (spanState.armedType) {
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

  // Document-level mouseup handler for drag span creation
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

      if (minIdx === maxIdx) {
        handleTokenClick(minIdx);
        return;
      }

      if (!spanState.armedType || !selectedTask || !docText) return;

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
    if (isDragging) setDragEndIndex(tokenIndex);
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
      if (!res.ok) toast("Failed to update span", "bad");
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
      if (!res.ok) toast("Failed to delete span", "bad");
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

  const selectedSpan = spanState.selectedSpanId
    ? spanState.confirmed.find((s) => s.id === spanState.selectedSpanId) ?? null
    : null;

  const confirmedCount = spanState.confirmed.filter((s) => !s.optimistic).length;
  const suggestedCount = spanState.suggested.length;
  const currentTaskStatus = selectedTask
    ? (taskStatuses[selectedTask.id] ?? selectedTask.status)
    : null;


  const armedEntityType = spanState.armedType
    ? entityTypes.find((et) => et.name === spanState.armedType)
    : null;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: layoutMode === "3pane" ? "228px 1fr 326px" : "1fr",
        gridTemplateRows: "auto auto 1fr auto",
        height: "100%",
        minHeight: 0,
        position: "relative",
      }}
      data-testid="annotation-workspace"
      data-layout={layoutMode}
    >
      {/* ── Toolbar (spans full width, always at top) ── */}
      <div style={{ gridColumn: "1 / -1", gridRow: 1 }}>
        <AnnotationToolbar
          task={selectedTask}
          filename={selectedTask?.filename ?? ""}
          currentStatus={currentTaskStatus}
          confirmedCount={confirmedCount}
          suggestedCount={suggestedCount}
          layoutMode={layoutMode}
          isPrelabeling={isPrelabeling}
          onStatusChange={handleStatusChange}
          onLayoutChange={handleLayoutChange}
          onPrelabel={handlePrelabel}
        />
      </div>

      {/* ── Armed Banner (below toolbar) ── */}
      {spanState.armedType && (
        <div style={{ gridColumn: "1 / -1", gridRow: 2 }}>
          <ArmedBanner
            entityType={spanState.armedType}
            description={armedEntityType?.description}
            onDisarm={() => dispatch({ type: "DISARM" })}
          />
        </div>
      )}

      {/* ── Left: Task Queue (3-pane only) ── */}
      {layoutMode === "3pane" && (
        <div
          style={{
            gridRow: "3 / 5",
            borderRight: "1px solid var(--color-border)",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
          }}
          data-testid="task-queue-column"
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
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span>Task Queue</span>
            {/* Task 3.2 — admin-only Assign Task button */}
            {isAdmin && (
              <button
                data-testid="assign-task-btn"
                onClick={() => setIsAssignFormOpen(true)}
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  background: "none",
                  border: "1px solid var(--color-primary, #6366f1)",
                  color: "var(--color-primary, #6366f1)",
                  borderRadius: 4,
                  padding: "2px 7px",
                  cursor: "pointer",
                  letterSpacing: 0,
                  textTransform: "none",
                }}
              >
                ＋ Assign Task
              </button>
            )}
          </div>
          {/* Task 3.3 — inline assignment form */}
          {isAdmin && isAssignFormOpen && (
            <AssignTaskForm
              onAssign={handleTaskAssigned}
              onCancel={() => setIsAssignFormOpen(false)}
            />
          )}
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

      {/* ── Center: Document Viewer ── */}
      <div
        style={{
          gridRow: "3 / 4",
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          overflowY: "auto",
          position: "relative",
          ...(layoutMode === "focus" ? { maxWidth: 760, margin: "0 auto", width: "100%" } : {}),
        }}
        data-testid="document-viewer-column"
      >
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px", position: "relative" }}>
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
        </div>
      </div>

      {/* ── Right: Entity Palette + Span Inspector (3-pane only) ── */}
      {layoutMode === "3pane" && (
        <div
          style={{
            gridRow: "3 / 5",
            borderLeft: "1px solid var(--color-border)",
            padding: "12px",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
          data-testid="entity-panel-column"
        >
          <EntityPalette
            entityTypes={entityTypes}
            entityColors={entityColors}
            confirmedSpans={spanState.confirmed}
            armedType={spanState.armedType}
            onArm={(name) => dispatch({ type: "ARM", entityType: name })}
            onDisarm={() => dispatch({ type: "DISARM" })}
          />
          {selectedSpan && layoutMode === "3pane" && (
            <SpanInspector
              span={selectedSpan}
              entityTypes={entityTypes}
              entityColors={entityColors}
              layoutMode="3pane"
              onRetype={handleRetype}
              onDelete={handleDelete}
              onClose={() => dispatch({ type: "SPAN_SET_SELECTED", spanId: null })}
            />
          )}
          {layoutMode === "3pane" && spanState.suggested.length > 0 && selectedTask && (
            <div>
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
      )}

      {/* ── Focus Mode: Floating Span Inspector ── */}
      {selectedSpan && layoutMode === "focus" && (
        <SpanInspector
          span={selectedSpan}
          entityTypes={entityTypes}
          entityColors={entityColors}
          layoutMode="focus"
          onRetype={handleRetype}
          onDelete={handleDelete}
          onClose={() => dispatch({ type: "SPAN_SET_SELECTED", spanId: null })}
        />
      )}

      {/* ── Focus Mode: Bottom Center Entity Palette ── */}
      {layoutMode === "focus" && (
        <FocusPalette
          entityTypes={entityTypes}
          entityColors={entityColors}
          confirmedSpans={spanState.confirmed}
          armedType={spanState.armedType}
          isPrelabeling={isPrelabeling}
          onArm={(name) => dispatch({ type: "ARM", entityType: name })}
          onDisarm={() => dispatch({ type: "DISARM" })}
          onPrelabel={handlePrelabel}
        />
      )}
    </div>
  );
}
