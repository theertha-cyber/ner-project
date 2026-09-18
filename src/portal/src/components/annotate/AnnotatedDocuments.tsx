"use client";

import type { CSSProperties } from "react";
import { AnnotationTask } from "@/components/annotation/TaskQueue";

interface AnnotatedDocumentsProps {
  tasks: AnnotationTask[];
  onView: (task: AnnotationTask) => void;
}

const sectionLabelStyle: CSSProperties = {
  fontFamily: "var(--font-mono, monospace)",
  fontSize: 10,
  fontWeight: 600,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "var(--ink-3)",
  marginTop: 26,
  marginBottom: 10,
};

export function AnnotatedDocuments({ tasks, onView }: AnnotatedDocumentsProps) {
  return (
    <>
      <div style={sectionLabelStyle}>Annotated documents</div>

      {tasks.length === 0 ? (
        <div
          style={{
            border: "1px solid var(--line)",
            borderRadius: 12,
            background: "var(--surface-2)",
            padding: "20px 16px",
            fontSize: 12.5,
            color: "var(--ink-3)",
          }}
        >
          Nothing annotated yet — assign a task and it will show up here once it&apos;s completed.
        </div>
      ) : (
        <div
          style={{
            border: "1px solid var(--line)",
            borderRadius: 12,
            background: "var(--surface-2)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 90px 70px",
              gap: 12,
              padding: "9px 16px",
              borderBottom: "1px solid var(--line)",
              fontSize: 10.5,
              fontWeight: 600,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              color: "var(--ink-3)",
            }}
          >
            <span>Document</span>
            <span>Spans</span>
            <span />
          </div>
          {tasks.map((task) => (
            <div
              key={task.id}
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 90px 70px",
                gap: 12,
                alignItems: "center",
                padding: "10px 16px",
                borderBottom: "1px solid var(--line-2, var(--line))",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                  fontSize: 12.5,
                  fontWeight: 500,
                  color: "var(--ink)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {task.filename}
              </span>
              <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12, color: "var(--ink-2)" }}>
                {task.span_count ?? 0}
              </span>
              <button
                onClick={() => onView(task)}
                style={{
                  justifySelf: "end",
                  background: "none",
                  border: "none",
                  color: "var(--color-primary, #a60000)",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  padding: 0,
                }}
              >
                View →
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
