"use client";

import { useState } from "react";
import { Spinner } from "@/components/ui";
import { useToast } from "@/hooks/use-toast";
import {
  usePromotionEvidence,
  useRequestRetrain,
  useRetrainingDecision,
} from "@/hooks/use-retraining";
import { useModelVersions } from "@/hooks/use-model-versions";
import type {
  EvaluationMetrics,
  PromotionEvidenceVersion,
} from "@/types/human-gated-retraining";

/**
 * A neutral chip, matching the review queue's.
 *
 * Deliberately not the shared status badge: its variants are a closed vocabulary of run states,
 * and a model version is not a state. Borrowing a status colour for one would make that palette
 * stop meaning anything.
 */
function Chip({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "warn";
}) {
  const toneClass =
    tone === "warn"
      ? "border-[var(--warning)] text-[var(--warning)]"
      : "border-[var(--border)] text-[var(--text-secondary)]";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs ${toneClass}`}>{children}</span>
  );
}

function metricRow(metrics: EvaluationMetrics, key: string): string {
  const value = metrics[key];
  if (typeof value !== "number") return "—";
  return value.toFixed(3);
}

/**
 * How much reviewed evidence has built up, per entity type, since the serving model was trained.
 *
 * The breakdown is the reason this is more than a number. A total of 134 spread evenly over
 * every entity type and 134 sitting almost entirely in one are the same figure and different
 * decisions, and there is no threshold here that would tell you which you are looking at —
 * ADR-010 records that even its own per-type readiness threshold is not empirically derived, and
 * inventing one for accumulation would be worse. The screen gives the decision structure and
 * stops.
 */
function AccumulationBreakdown() {
  const { data, isLoading, error } = useRetrainingDecision();
  const { toast } = useToast();
  const requestRetrain = useRequestRetrain();

  if (isLoading) return <Spinner />;
  if (error) return <p className="text-sm text-[var(--danger)]">{error.message}</p>;
  if (!data) return null;

  const onRequest = () => {
    requestRetrain.mutate(undefined, {
      onSuccess: (result) => {
        toast(
          result.warnedNoAccumulation
            ? "Retrain requested, but no new reviewed evidence has accumulated since this model was trained. It is waiting for System Admin approval — over unchanged data, a retrain only differs if the hyperparameters do."
            : "Retrain requested. It is waiting for System Admin approval; nothing trains until then.",
          "ok",
        );
      },
      onError: (err) => toast(err.message, "bad"),
    });
  };

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <header className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Production-review evidence
        </h2>
        {data.has_trained_model ? (
          <Chip>Model version {data.serving_model_version}</Chip>
        ) : (
          <Chip>Base model</Chip>
        )}
      </header>
      <p className="mt-1 text-xs text-[var(--text-tertiary)]">
        Counts only spans confirmed through production review — someone checking a live
        prediction and confirming or correcting it. It does not include manual annotation,
        automated batches, or imports; those are counted separately below.
      </p>

      {data.has_trained_model ? (
        <>
          <p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">
            {data.spans_accumulated}
          </p>
          <p className="text-sm text-[var(--text-secondary)]">
            confirmed {data.spans_accumulated === 1 ? "span" : "spans"} from production review
            since version {data.serving_model_version} was trained
          </p>

          {Object.keys(data.by_entity_type).length > 0 && (
            <table className="mt-4 w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-[var(--text-tertiary)]">
                  <th className="pb-1 font-medium">Entity type</th>
                  <th className="pb-1 text-right font-medium">Accumulated</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.by_entity_type).map(([entityType, count]) => (
                  <tr key={entityType} className="border-t border-[var(--border)]">
                    <td className="py-1.5 text-[var(--text-primary)]">{entityType}</td>
                    <td className="py-1.5 text-right tabular-nums text-[var(--text-primary)]">
                      {count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {data.spans_accumulated > 0 && (
            <p className="mt-2 text-xs text-[var(--text-tertiary)]">
              By source: {data.by_source.manual} manual · {data.by_source.automated} from
              accepted automated batches
            </p>
          )}

          {data.spans_from_base_model > 0 && (
            <p className="mt-3 text-xs text-[var(--text-tertiary)]">
              A further {data.spans_from_base_model} came from base-model predictions and are not
              counted here.
            </p>
          )}
        </>
      ) : (
        /* Not a zero. A tenant with no trained model and a tenant that has just retrained both
           have "nothing new", and only one of them should do nothing about it. */
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          {data.state_detail}{" "}
          {data.spans_from_base_model > 0 &&
            `${data.spans_from_base_model} reviewed ${
              data.spans_from_base_model === 1 ? "span" : "spans"
            } came from base-model predictions and are recorded separately.`}
        </p>
      )}

      {data.training_run_in_flight && (
        <p className="mt-3 rounded border border-[var(--warning)] px-3 py-2 text-xs text-[var(--text-secondary)]">
          {data.in_flight_detail}
        </p>
      )}

      {(() => {
        const o = data.eligible_overview;
        const total = o.manual.count + o.automated.count + o.import.count;
        return (
          <div className="mt-4 border-t border-[var(--border)] pt-4">
            <p className="text-xs uppercase text-[var(--text-tertiary)]">
              Training-eligible and waiting
            </p>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">
              A separate count: new material from any workflow that no training run has
              consumed yet, regardless of the production-review number above.
            </p>
            {total === 0 ? (
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                Nothing new since the last training run.
              </p>
            ) : (
              <ul className="mt-1 text-sm text-[var(--text-primary)]">
                <li>{o.manual.count} completed manual annotation task{o.manual.count === 1 ? "" : "s"}</li>
                <li>{o.automated.count} annotator-approved automated batch{o.automated.count === 1 ? "" : "es"}</li>
                <li>{o.import.count} mapped import file{o.import.count === 1 ? "" : "s"}</li>
              </ul>
            )}
          </div>
        );
      })()}

      <div className="mt-4 flex items-center gap-3 border-t border-[var(--border)] pt-4">
        <button
          type="button"
          onClick={onRequest}
          disabled={requestRetrain.isPending}
          className="rounded bg-[var(--accent)] px-3 py-1.5 text-sm text-white disabled:opacity-40"
        >
          {requestRetrain.isPending ? "Requesting…" : "Request a retrain"}
        </button>
        <span className="text-xs text-[var(--text-tertiary)]">
          Creates a training job awaiting System Admin approval. Nothing trains until it is
          approved and the hyperparameters are set.
        </span>
      </div>

      <p className="mt-3 border-t border-[var(--border)] pt-3 text-xs text-[var(--text-tertiary)]">
        {data.note} Nothing is started automatically by this number growing — a retrain happens
        only when someone requests one and a System Admin approves it.
      </p>
    </section>
  );
}

function VersionColumn({
  heading,
  version,
}: {
  heading: string;
  version: PromotionEvidenceVersion;
}) {
  return (
    <div className="flex-1 rounded-lg border border-[var(--border)] p-3">
      <p className="text-xs uppercase text-[var(--text-tertiary)]">{heading}</p>
      <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
        Version {version.version_number}
      </p>
      <dl className="mt-2 space-y-1 text-sm">
        {(["eval_f1", "eval_precision", "eval_recall", "eval_loss"] as const).map((key) => (
          <div key={key} className="flex justify-between gap-4">
            <dt className="text-[var(--text-secondary)]">{key.replace("eval_", "")}</dt>
            <dd className="tabular-nums text-[var(--text-primary)]">
              {metricRow(version.metrics, key)}
            </dd>
          </div>
        ))}
        <div className="flex justify-between gap-4 border-t border-[var(--border)] pt-1">
          <dt className="text-[var(--text-secondary)]">trained on</dt>
          <dd className="tabular-nums text-[var(--text-primary)]">
            {version.trained_on_span_count > 0
              ? `${version.trained_on_span_count} spans`
              : "not recorded"}
          </dd>
        </div>
      </dl>
    </div>
  );
}

/**
 * A candidate version's metrics beside the serving version's.
 *
 * There is no verdict here and no "promote" button. Promotion stays where it already was — the
 * models screen — and this exists only so that decision is made on something more than the fact
 * that a run finished.
 *
 * The comparability line is not decoration. Change 3 established that metrics from runs over
 * materially different data are not comparable, and two numbers side by side invite a comparison
 * whether or not one is valid. A surface that silently invited an invalid one would be worse
 * than showing nothing: it produces confident wrong promotions rather than uncertain ones.
 */
function PromotionEvidencePanel({ versionNumber }: { versionNumber: number }) {
  const { data, isLoading, error } = usePromotionEvidence(versionNumber);

  if (isLoading) return <Spinner />;
  if (error) return <p className="text-sm text-[var(--danger)]">{error.message}</p>;
  if (!data) return null;

  return (
    <div className="mt-3">
      <div className="flex flex-col gap-3 sm:flex-row">
        <VersionColumn heading="Candidate" version={data.candidate} />
        {data.current ? (
          <VersionColumn heading="Currently serving" version={data.current} />
        ) : (
          <div className="flex-1 rounded-lg border border-dashed border-[var(--border)] p-3 text-sm text-[var(--text-secondary)]">
            No other promoted version to compare against.
          </div>
        )}
      </div>

      <p
        className={`mt-3 rounded border px-3 py-2 text-xs ${
          data.comparable === false
            ? "border-[var(--warning)] text-[var(--text-secondary)]"
            : "border-[var(--border)] text-[var(--text-tertiary)]"
        }`}
      >
        {data.note}
      </p>
    </div>
  );
}

/**
 * The retraining and promotion decision surfaces.
 *
 * Both live here rather than on the models screen, which keeps the existing promote control and
 * the training jobs and approval screens exactly as they are. Nothing on this page promotes,
 * approves, or starts anything: it asks, and it shows what the asking should be based on.
 */
export function RetrainingDecisionPage() {
  const { data: versions } = useModelVersions();
  const [selected, setSelected] = useState<number | null>(null);

  // Versions a run finished and nobody has promoted, newest first — the ones a promotion
  // decision is actually about. Read from the model registry the models screen already reads,
  // so the two screens cannot disagree about which versions exist.
  const completedVersions = (versions ?? [])
    .filter((version) => version.status === "completed")
    .map((version) => version.version_number)
    .sort((a, b) => b - a);

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">Retraining</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          What has been reviewed since the serving model was trained, and how a finished run
          compares with the one currently serving. Both are evidence for a decision a person
          makes — nothing here trains or promotes on its own. There is no schedule and no
          required order: come back whenever you want to check, and retrain only when you decide
          it is worth it.
        </p>
      </header>

      <AccumulationBreakdown />

      <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Promotion evidence
        </h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Pick a completed run to see its metrics beside the serving version&apos;s. Promoting is
          done from the models screen.
        </p>

        {completedVersions.length === 0 ? (
          <p className="mt-3 rounded-xl border border-dashed border-[var(--border)] p-6 text-center text-sm text-[var(--text-secondary)]">
            No completed runs yet.
          </p>
        ) : (
          <>
            <div className="mt-3 flex flex-wrap gap-2">
              {completedVersions.map((versionNumber) => (
                <button
                  key={versionNumber}
                  type="button"
                  onClick={() =>
                    setSelected(selected === versionNumber ? null : versionNumber)
                  }
                  className={`rounded border px-3 py-1.5 text-sm ${
                    selected === versionNumber
                      ? "border-[var(--accent)] text-[var(--accent)]"
                      : "border-[var(--border)] text-[var(--text-secondary)]"
                  }`}
                >
                  Version {versionNumber}
                </button>
              ))}
            </div>
            {selected !== null && <PromotionEvidencePanel versionNumber={selected} />}
          </>
        )}
      </section>
    </div>
  );
}
