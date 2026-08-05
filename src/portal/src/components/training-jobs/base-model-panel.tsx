import { BASE_MODEL_NAME } from "./base-model-card";

const CONLL_LABELS = ["PER", "ORG", "LOC", "MISC"];

export function BaseModelPanel() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-lg font-semibold" style={{ color: "var(--ink)" }}>
          Base Model
        </h2>
        <p className="font-mono text-xs" style={{ color: "var(--ink-3)" }}>
          {BASE_MODEL_NAME}
        </p>
      </div>

      <section>
        <h3 className="mb-2 font-body text-sm font-semibold" style={{ color: "var(--ink-2)" }}>
          Supported Labels
        </h3>
        <div className="flex flex-wrap gap-1.5">
          {CONLL_LABELS.map((label) => (
            <span
              key={label}
              className="rounded-full px-2.5 py-0.5 font-body text-xs font-medium"
              style={{ background: "var(--surface-3)", color: "var(--ink-2)" }}
            >
              {label}
            </span>
          ))}
        </div>
        <p className="mt-2 font-body text-xs" style={{ color: "var(--ink-3)" }}>
          Shared base model — no fine-tuning required. Serves all tenants until a custom model is
          promoted.
        </p>
      </section>
    </div>
  );
}
