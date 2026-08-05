import { Badge } from "@/components/ui";

export const BASE_MODEL_ID = "v0-base";
export const BASE_MODEL_NAME = "dslim/bert-base-NER";

export interface BaseModelCardProps {
  isActive: boolean;
  isSelected: boolean;
  onClick: () => void;
}

export function BaseModelCard({ isActive, isSelected, onClick }: BaseModelCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-lg p-3 text-left transition-colors"
      style={{
        border: `1px solid ${isSelected ? "var(--primary-line)" : "var(--line)"}`,
        background: isSelected ? "var(--primary-soft)" : "var(--surface-2)",
      }}
    >
      <div className="mb-1.5 flex items-center gap-2">
        <span className="font-mono text-xs font-semibold" style={{ color: "var(--ink)" }}>
          Base Model
        </span>
        <div className="flex-1" />
        {isActive && <span className="inline-block h-2 w-2 rounded-full bg-status-promoted" />}
        <Badge variant={isActive ? "promoted" : "archived"} />
      </div>
      <p className="font-mono text-xs italic" style={{ color: "var(--ink-3)" }}>
        {BASE_MODEL_NAME}
      </p>
    </button>
  );
}
