import type { TrainingJob } from "@/types/training-jobs";
import { getTimeline } from "@/lib/training-jobs";
import { useModelVersions } from "@/hooks/use-model-versions";
import { JobTimeline } from "./job-timeline";
import { JobMetrics } from "./job-metrics";
import { JobProgress } from "./job-progress";
import { ModelVersionSection } from "./model-version-section";
import { Spinner, Badge, LineageFlow } from "@/components/ui";

export interface JobDetailPanelProps {
  job: TrainingJob | undefined;
  isLoading: boolean;
  isError: boolean;
  hasSelection?: boolean;
  defaultEpochs?: number;
  viewerRole?: string;
}

function truncateUrl(url: string, max = 44): string {
  return url.length > max ? `${url.slice(0, max)}…` : url;
}

export function JobDetailPanel({
  job,
  isLoading,
  isError,
  hasSelection = true,
  defaultEpochs = 3,
  viewerRole,
}: JobDetailPanelProps) {
  const { data: modelVersions, activeModel } = useModelVersions(viewerRole, job?.tenant_id);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner />
      </div>
    );
  }

  if (!hasSelection) {
    return (
      <div
        className="rounded-lg p-4"
        style={{ background: "var(--surface-3)", border: "1px solid var(--line)" }}
      >
        <p className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
          No job selected
        </p>
      </div>
    );
  }

  if (isError || !job) {
    return (
      <div
        className="rounded-lg p-4"
        style={{ background: "var(--bad-soft)", border: "1px solid var(--bad)" }}
      >
        <p className="font-body text-sm" style={{ color: "var(--bad)" }}>
          Job not found
        </p>
      </div>
    );
  }

  const timeline = getTimeline(job.status);
  const hyperparams = job.hyperparams;
  const matchedVersion = modelVersions?.find((v) => v.training_job_id === job.id);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <span className="font-mono text-base font-semibold" style={{ color: "var(--ink)" }}>
          {job.run_name ?? job.id}
        </span>
        <Badge variant={job.status} />
        <div className="flex-1" />
        {job.created_at && (
          <span className="font-mono text-xs" style={{ color: "var(--ink-3)" }}>
            {new Date(job.created_at).toLocaleDateString(undefined, {
              year: "numeric",
              month: "2-digit",
              day: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        )}
      </div>

      {/* Status Timeline */}
      <section>
        <h3 className="mb-2 font-body text-sm font-semibold" style={{ color: "var(--ink-2)" }}>
          Status
        </h3>
        <JobTimeline steps={timeline} currentStatus={job.status} />
      </section>

      {/* Lineage */}
      <section>
        <h3 className="mb-2 font-body text-sm font-semibold" style={{ color: "var(--ink-2)" }}>
          Lineage
        </h3>
        <LineageFlow
          nodes={[
            { label: "DATASET", value: "Annotated Documents" },
            { label: "TRAINING JOB", value: job.run_name ?? job.id, sublabel: "dslim/bert-base-NER" },
            {
              label: "MODEL VERSION",
              value: matchedVersion
                ? matchedVersion.run_name ?? `v${matchedVersion.version_number}`
                : null,
              sublabel: "registry",
            },
          ]}
          emphasizedIndex={1}
        />
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
      <section>
        <h3 className="mb-2 font-body text-sm font-semibold" style={{ color: "var(--ink-2)" }}>
          Hyperparameters
        </h3>
        {hyperparams ? (
          <div className="grid grid-cols-4 gap-2 text-xs">
            <div className="rounded p-2" style={{ background: "var(--surface-3)" }}>
              <span className="font-body" style={{ color: "var(--ink-3)" }}>Learning Rate</span>
              <p className="font-mono font-medium" style={{ color: "var(--ink)" }}>{hyperparams.learning_rate}</p>
            </div>
            <div className="rounded p-2" style={{ background: "var(--surface-3)" }}>
              <span className="font-body" style={{ color: "var(--ink-3)" }}>Epochs</span>
              <p className="font-mono font-medium" style={{ color: "var(--ink)" }}>{hyperparams.num_epochs}</p>
            </div>
            <div className="rounded p-2" style={{ background: "var(--surface-3)" }}>
              <span className="font-body" style={{ color: "var(--ink-3)" }}>Batch Size</span>
              <p className="font-mono font-medium" style={{ color: "var(--ink)" }}>{hyperparams.batch_size}</p>
            </div>
            <div className="rounded p-2" style={{ background: "var(--surface-3)" }}>
              <span className="font-body" style={{ color: "var(--ink-3)" }}>Max Seq Length</span>
              <p className="font-mono font-medium" style={{ color: "var(--ink)" }}>{hyperparams.max_seq_length}</p>
            </div>
          </div>
        ) : (
          <p
            className="rounded-lg p-3 font-body text-sm"
            style={{ background: "var(--surface-3)", border: "1px solid var(--line)", color: "var(--ink-3)" }}
          >
            Hyperparameters not yet set — awaiting System Admin approval
          </p>
        )}
      </section>

      {/* Metrics */}
      {job.metrics && <JobMetrics metrics={job.metrics} />}

      {/* Model version produced by this job */}
      {matchedVersion && (
        <ModelVersionSection
          model={matchedVersion}
          isActive={activeModel?.id === matchedVersion.id}
        />
      )}

      {/* Error */}
      {job.status === "failed" && job.error_message && (
        <div className="rounded-lg p-3" style={{ background: "var(--bad-soft)", border: "1px solid var(--bad)" }}>
          <p className="font-body text-xs font-medium" style={{ color: "var(--bad)" }}>Error</p>
          <p className="mt-1 font-body text-sm" style={{ color: "var(--ink)" }}>{job.error_message}</p>
        </div>
      )}

      {/* MLflow Link */}
      {job.mlflow_run_url && (
        <section>
          <h3 className="mb-1 font-body text-sm font-semibold" style={{ color: "var(--ink-2)" }}>
            MLflow Run
          </h3>
          <a
            href={job.mlflow_run_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg p-3 transition-colors"
            style={{ background: "var(--surface-2)", border: "1px solid var(--line)" }}
          >
            <span aria-hidden="true">⎘</span>
            <div className="min-w-0">
              <p className="font-body text-sm font-medium" style={{ color: "var(--ink)" }}>MLflow run</p>
              <p className="truncate font-mono text-xs" style={{ color: "var(--ink-3)" }}>
                {truncateUrl(job.mlflow_run_url)}
              </p>
            </div>
          </a>
        </section>
      )}
    </div>
  );
}
