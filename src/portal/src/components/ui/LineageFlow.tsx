"use client";

export interface LineageNode {
  label: string;
  value: string | number | null | undefined;
  sublabel?: string;
}

export interface LineageFlowProps {
  nodes: LineageNode[];
  emphasizedIndex?: number;
  fallbackValue?: string;
}

export function LineageFlow({ nodes, emphasizedIndex, fallbackValue = "pending" }: LineageFlowProps) {
  return (
    <div className="flex items-stretch gap-2" role="group" aria-label="Lineage">
      {nodes.map((node, i) => {
        const emphasized = i === emphasizedIndex;
        return (
          <div key={node.label} className="flex flex-1 items-stretch gap-2">
            <div
              data-testid="lineage-node"
              data-emphasized={emphasized}
              className="flex flex-1 flex-col justify-center rounded-lg px-3 py-2"
              style={{
                background: emphasized ? "var(--primary-soft)" : "var(--surface-2)",
                border: `1px solid ${emphasized ? "var(--primary-line)" : "var(--line)"}`,
              }}
            >
              <span
                className="font-mono uppercase tracking-wide"
                style={{
                  fontSize: 10,
                  color: emphasized ? "var(--primary)" : "var(--ink-3)",
                }}
              >
                {node.label}
              </span>
              <span
                className="font-mono truncate"
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: emphasized ? "var(--primary)" : "var(--ink)",
                }}
              >
                {node.value === null || node.value === undefined || node.value === ""
                  ? fallbackValue
                  : node.value}
              </span>
              {node.sublabel && (
                <span className="font-mono" style={{ fontSize: 10, color: "var(--ink-3)" }}>
                  {node.sublabel}
                </span>
              )}
            </div>
            {i < nodes.length - 1 && (
              <div
                data-testid="lineage-arrow"
                className="flex shrink-0 items-center"
                style={{ color: "var(--ink-3)" }}
                aria-hidden="true"
              >
                →
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
