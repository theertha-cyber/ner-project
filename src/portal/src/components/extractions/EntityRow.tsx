import type { EntityItem } from "@/types/extraction";

function cleanEntityType(label: string): string {
  return label.replace(/^[BI]-/, "");
}

const ENTITY_COLORS: Record<string, string> = {
  PER: "#6366f1",
  ORG: "#f59e0b",
  LOC: "#10b981",
  MISC: "#8b5cf6",
};

function entityDotColor(type: string): string {
  return ENTITY_COLORS[type] ?? "#94a3b8";
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.9) return "text-success";
  if (confidence >= 0.7) return "text-warning";
  return "text-error";
}

const REVIEW_PILL: Record<string, string> = {
  unreviewed: "bg-border text-text-secondary",
  confirmed: "bg-status-completed/20 text-status-completed",
  rejected: "bg-status-failed/20 text-status-failed",
  corrected: "bg-status-running/20 text-status-running",
};

export interface EntityRowProps {
  entity: EntityItem;
  onConfirm: (id: string) => void;
  onReject: (id: string) => void;
}

export function EntityRow({ entity, onConfirm, onReject }: EntityRowProps) {
  const isReviewed =
    entity.review_status === "confirmed" || entity.review_status === "rejected";

  return (
    <div className="flex items-center gap-3 px-3 py-2">
      {/* VALUE + filename */}
      <div className="flex flex-col min-w-0 flex-1">
        <span className="font-semibold text-sm text-text-primary truncate">{entity.value}</span>
        {entity.document_filename && (
          <span className="text-xs text-text-secondary truncate">{entity.document_filename}</span>
        )}
      </div>

      {/* CONFIDENCE */}
      <span className={`text-sm tabular-nums font-medium ${confidenceColor(entity.confidence)}`}>
        {entity.confidence.toFixed(3)}
      </span>

      {/* REVIEW STATUS */}
      <span
        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${REVIEW_PILL[entity.review_status] ?? "bg-border text-text-secondary"}`}
      >
        {entity.review_status}
      </span>

      {/* ACTIONS */}
      {!isReviewed ? (
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onConfirm(entity.id)}
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-border text-success hover:bg-status-completed/10 transition-colors"
            aria-label="Confirm entity"
          >
            ✓
          </button>
          <button
            type="button"
            onClick={() => onReject(entity.id)}
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-border text-error hover:bg-status-failed/10 transition-colors"
            aria-label="Reject entity"
          >
            ✗
          </button>
        </div>
      ) : (
        <div className="w-16" />
      )}
    </div>
  );
}
