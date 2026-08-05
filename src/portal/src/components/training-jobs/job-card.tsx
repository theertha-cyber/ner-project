import type { TrainingJob } from "@/types/training-jobs";
import { Badge, badgeDotClass } from "@/components/ui";

export interface JobCardProps {
  job: TrainingJob;
  isSelected: boolean;
  onClick: () => void;
}

function formatHyperparams(job: TrainingJob): string {
  const hp = job.hyperparams;
  if (!hp) return "awaiting hyperparameters";
  return `lr ${hp.learning_rate} · ${hp.num_epochs}ep · bs ${hp.batch_size}`;
}

function formatF1(job: TrainingJob): string {
  const f1 = job.metrics?.eval_f1;
  return typeof f1 === "number" ? f1.toFixed(2) : "—";
}

export function JobCard({ job, isSelected, onClick }: JobCardProps) {
  const isRunning = job.status === "running";
  const hyperparamLine = formatHyperparams(job);

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
        <span
          className={`inline-block h-2 w-2 shrink-0 rounded-full ${badgeDotClass(job.status)} ${isRunning ? "animate-pulse" : ""}`}
        />
        <span className="font-mono text-xs font-semibold" style={{ color: "var(--ink)" }}>
          {job.run_name ?? job.id}
        </span>
        <div className="flex-1" />
        <Badge variant={job.status} />
      </div>
      <div className="flex items-center justify-between">
        <p className="font-mono text-xs" style={{ color: "var(--ink-3)" }}>
          {hyperparamLine}
        </p>
        <p className="font-mono text-xs" style={{ color: "var(--ink-2)" }}>
          F1 {formatF1(job)}
        </p>
      </div>
    </button>
  );
}
