"use client";

export interface AnnotationTask {
  id: string;
  document_id: string;
  annotator_user_id: string;
  status: "unannotated" | "in-progress" | "completed";
  created_at: string;
  updated_at: string | null;
  filename: string;
  document_status?: string;
  span_count?: number;
}

interface TaskQueueProps {
  tasks: AnnotationTask[];
  selectedTaskId: string | null;
  taskStatuses: Record<string, AnnotationTask["status"]>;
  onSelect: (task: AnnotationTask) => void;
}

const STATUS_COLORS: Record<AnnotationTask["status"], string> = {
  unannotated: "var(--color-text-secondary)",
  "in-progress": "var(--color-primary)",
  completed: "var(--color-success, #10b981)",
};

export function TaskQueue({ tasks, selectedTaskId, taskStatuses, onSelect }: TaskQueueProps) {
  if (tasks.length === 0) {
    return (
      <div
        style={{
          padding: "32px 16px",
          textAlign: "center",
          color: "var(--color-text-secondary)",
          fontSize: 13,
        }}
      >
        <div style={{ fontSize: 24, marginBottom: 8 }}>✎</div>
        <div>No tasks assigned</div>
        <div style={{ marginTop: 6, fontSize: 12 }}>Contact a tenant admin to get started</div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {tasks.map((task) => {
        const status = taskStatuses[task.id] ?? task.status;
        const isSelected = task.id === selectedTaskId;
        const subtitle = task.document_status
          ? `${task.document_status} · ${task.span_count ?? 0} spans`
          : status.replace("-", " ");

        return (
          <button
            key={task.id}
            onClick={() => onSelect(task)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 12px",
              border: "none",
              borderRadius: 6,
              background: isSelected ? "var(--color-primary-soft, rgba(99,102,241,0.12))" : "transparent",
              cursor: "pointer",
              textAlign: "left",
              width: "100%",
              borderLeft: isSelected ? "3px solid var(--color-primary)" : "3px solid transparent",
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 500,
                  fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                  color: "var(--color-text-primary)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {task.filename}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: STATUS_COLORS[status],
                  marginTop: 2,
                }}
              >
                {subtitle}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
