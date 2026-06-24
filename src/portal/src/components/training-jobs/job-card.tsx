import type { TrainingJob } from "@/types/training-jobs";
import { Badge } from "@/components/ui";

export interface JobCardProps {
  job: TrainingJob;
  isSelected: boolean;
  onClick: () => void;
}

export function JobCard({ job, isSelected, onClick }: JobCardProps) {
  const isRunning = job.status === "running";
  const dateStr = job.created_at
    ? new Date(job.created_at).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "w-full rounded-lg border p-3 text-left transition-colors",
        isSelected
          ? "border-brand-primary bg-brand-primary/5"
          : "border-border hover:border-brand-primary/50",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-2">
        <Badge variant={job.status} />
        {isRunning && (
          <span className="inline-block h-2 w-2 rounded-full bg-status-running animate-pulse" />
        )}
      </div>
      {dateStr && (
        <p className="mt-1 text-xs text-gray-500">{dateStr}</p>
      )}
    </button>
  );
}
