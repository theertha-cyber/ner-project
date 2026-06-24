import type { TrainingJob } from "@/types/training-jobs";
import { getTimeline } from "@/lib/training-jobs";
import { JobTimeline } from "./job-timeline";
import { JobMetrics } from "./job-metrics";
import { JobProgress } from "./job-progress";
import { Spinner, Badge } from "@/components/ui";

export interface JobDetailPanelProps {
  job: TrainingJob | undefined;
  isLoading: boolean;
  isError: boolean;
  defaultEpochs?: number;
}

export function JobDetailPanel({
  job,
  isLoading,
  isError,
  defaultEpochs = 3,
}: JobDetailPanelProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner />
      </div>
    );
  }

  if (isError || !job) {
    return (
      <div className="rounded-lg border border-status-failed/30 bg-status-failed/5 p-4">
        <p className="text-sm text-status-failed">Job not found</p>
      </div>
    );
  }

  const timeline = getTimeline(job.status);
  const hyperparams = job.hyperparams;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Badge variant={job.status} />
        <span className="text-xs text-gray-400">{job.id.slice(0, 8)}</span>
      </div>

      {/* Status Timeline */}
      <section>
        <h3 className="mb-2 text-sm font-semibold text-gray-700">Status</h3>
        <JobTimeline steps={timeline} />
      </section>

      {/* Running Progress */}
      {job.status === "running" && (
        <JobProgress
          currentEpoch={job.current_epoch}
          currentLoss={job.current_loss}
          numEpochs={hyperparams?.num_epochs ?? defaultEpochs}
        />
      )}

      {/* Hyperparameters */}
      {hyperparams && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-gray-700">Hyperparameters</h3>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded bg-gray-50 p-2">
              <span className="text-gray-500">Learning Rate</span>
              <p className="font-medium text-gray-900">{hyperparams.learning_rate}</p>
            </div>
            <div className="rounded bg-gray-50 p-2">
              <span className="text-gray-500">Epochs</span>
              <p className="font-medium text-gray-900">{hyperparams.num_epochs}</p>
            </div>
            <div className="rounded bg-gray-50 p-2">
              <span className="text-gray-500">Batch Size</span>
              <p className="font-medium text-gray-900">{hyperparams.batch_size}</p>
            </div>
            <div className="rounded bg-gray-50 p-2">
              <span className="text-gray-500">Max Seq Length</span>
              <p className="font-medium text-gray-900">{hyperparams.max_seq_length}</p>
            </div>
          </div>
        </section>
      )}

      {/* Metrics */}
      {job.metrics && <JobMetrics metrics={job.metrics} />}

      {/* Error */}
      {job.status === "failed" && job.error_message && (
        <div className="rounded-lg border border-status-failed/30 bg-status-failed/5 p-3">
          <p className="text-xs font-medium text-status-failed">Error</p>
          <p className="mt-1 text-sm text-gray-700">{job.error_message}</p>
        </div>
      )}

      {/* MLflow Link */}
      {job.mlflow_run_url && (
        <section>
          <h3 className="mb-1 text-sm font-semibold text-gray-700">MLflow Run</h3>
          <a
            href={job.mlflow_run_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-brand-primary underline hover:text-brand-primary/80"
          >
            View in MLflow
          </a>
        </section>
      )}
    </div>
  );
}
