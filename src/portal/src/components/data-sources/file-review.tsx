"use client";

import { useState, type CSSProperties, type ReactNode } from "react";
import {
  useTabularProfile,
  useTabularPublish,
  useTabularReview,
  type SafeApiHttpError,
} from "@/hooks/use-data-sources";
import {
  TABULAR_BLOCKER_MESSAGES,
  TABULAR_COLUMN_TYPES,
  TABULAR_DATE_FORMATS,
  tabularErrorMessage,
  type TabularColumnEdit,
  type TabularProfileColumn,
  type TabularReviewColumn,
  type TabularReviewEdit,
} from "@/lib/data-sources";

// Form controls take the theme's surface and ink explicitly: left to the browser
// default they render white in dark mode while inheriting the light ink colour,
// which makes typed text invisible.
const FIELD_STYLE: CSSProperties = {
  border: "1px solid var(--line)",
  background: "var(--surface-2)",
  color: "var(--ink)",
};
const FIELD_CLASS = "w-full rounded-md px-3 py-2 text-sm outline-none focus-visible:ring-2";
const COMPACT_FIELD_CLASS = "w-full min-w-0 rounded-md px-2 py-1.5 text-sm outline-none focus-visible:ring-2";
const CARD_STYLE: CSSProperties = { border: "1px solid var(--line)", background: "var(--surface-2)" };

/**
 * Review of one pending version before publish (tabular-file-ingestion spec):
 * per-column identifier, type, date format, exclusion, description and value
 * hints; table description and null tokens; the load report and 20-row typed
 * preview the server recomputes on every change; the schema diff for a version
 * after the first; and a publish control disabled while any blocker is listed.
 */
export function FileReview({
  fileId,
  version,
  onClose,
  onPublished,
}: {
  fileId: string;
  version: number;
  onClose: () => void;
  onPublished: () => void;
}) {
  const { data, isLoading, isError } = useTabularProfile(fileId, version);
  const review = useTabularReview(fileId, version);
  const publish = useTabularPublish(fileId, version);
  const [editError, setEditError] = useState<string | null>(null);

  if (isLoading)
    return (
      <p role="status" className="text-sm" style={{ color: "var(--ink-2)" }}>
        Loading review…
      </p>
    );
  if (isError || !data || !data.review || !data.profile) {
    return (
      <div className="flex flex-col gap-2">
        <p role="status" className="text-sm" style={{ color: "var(--ink-2)" }}>
          This version cannot be reviewed right now.
        </p>
        <button type="button" className="self-start text-sm underline" style={{ color: "var(--ink)" }} onClick={onClose}>
          Back to uploaded files
        </button>
      </div>
    );
  }

  const profileById = new Map<number, TabularProfileColumn>(data.profile.columns.map((c) => [c.index, c]));
  const report = data.load_report;
  const blockers = data.blockers ?? [];
  // The preview's object keys arrive in whatever order the server serialised them;
  // show them in the file's own column order so it lines up with the table above.
  const previewKeys = report?.preview.length
    ? orderedPreviewKeys(Object.keys(report.preview[0]), data.review.columns)
    : [];

  function send(edit: TabularReviewEdit) {
    setEditError(null);
    review.mutate(
      { edit },
      {
        onError: (err) => {
          const e = err as SafeApiHttpError;
          setEditError(e.code === "INVALID_REQUEST" ? "That change was refused; check the field and try again." : tabularErrorMessage(e.code));
        },
      },
    );
  }

  function column(edit: TabularColumnEdit) {
    send({ columns: [edit] });
  }

  return (
    <div className="flex flex-col gap-6" aria-label={`Review ${data.file.display_name} version ${version}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold" style={{ color: "var(--ink)" }}>
            Review {data.file.display_name} — version {version}
          </h3>
          <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
            Table <code className="rounded px-1.5 py-0.5 font-mono text-xs" style={{ background: "var(--surface-3)", color: "var(--ink)" }}>{data.review.table.relation}</code>
            {data.sheet ? <> · sheet {data.sheet}</> : null} · {data.profile.row_count.toLocaleString()} rows
          </p>
          <p className="mt-2 max-w-[75ch] text-sm leading-6" style={{ color: "var(--ink-2)" }}>
            Check how each column was read, then publish. Chat only ever sees what you publish here: the table and
            column names, their types, your descriptions, and any values you tick as hints — never the rows themselves.
          </p>
        </div>
        <button
          type="button"
          className="rounded-md px-3 py-1.5 text-sm font-medium outline-none focus-visible:ring-2"
          style={{ border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
          onClick={onClose}
        >
          Back
        </button>
      </div>

      <Card title="About this table" hint="The table description is required and is what the chat assistant reads first when deciding whether this file can answer a question.">
        <div className="grid gap-5 md:grid-cols-2">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium" style={{ color: "var(--ink)" }}>
              Table description (required)
            </span>
            <textarea
              aria-label="Table description"
              rows={3}
              placeholder="e.g. Q3 2026 sales deals, one row per deal"
              defaultValue={data.review.table.description}
              onBlur={(e) => {
                if (e.target.value !== data.review?.table.description) send({ table: { description: e.target.value } });
              }}
              className={`${FIELD_CLASS} resize-y`}
              style={FIELD_STYLE}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium" style={{ color: "var(--ink)" }}>
              Null tokens (comma-separated)
            </span>
            <input
              aria-label="Null tokens"
              defaultValue={data.review.table.null_tokens.join(", ")}
              onBlur={(e) => {
                const tokens = e.target.value.split(",").map((t) => t.trim());
                send({ table: { null_tokens: tokens } });
              }}
              className={FIELD_CLASS}
              style={FIELD_STYLE}
            />
            <span className="text-xs leading-5" style={{ color: "var(--ink-3)" }}>
              Cell values treated as empty. The leading comma stands for a blank cell.
            </span>
          </label>
        </div>
      </Card>

      {editError && (
        <p role="alert" className="rounded-md px-3 py-2 text-sm" style={{ border: "1px solid var(--primary-line)", background: "var(--primary-soft)", color: "var(--ink)" }}>
          {editError}
        </p>
      )}

      <Card title="Columns" hint="One row per column in your file. Changes save when you leave a field.">
        <dl className="mb-4 grid gap-x-6 gap-y-2 text-xs leading-5 sm:grid-cols-2 lg:grid-cols-3" style={{ color: "var(--ink-2)" }}>
          <Legend term="Identifier">The name chat&apos;s queries use. Lowercase letters, digits and underscores.</Legend>
          <Legend term="Type">How values are stored. Values that don&apos;t fit are rejected in the load report.</Legend>
          <Legend term="Description">Optional, but it helps chat pick the right column.</Legend>
          <Legend term="Value hints">
            Tick the values people will filter by. They&apos;re shared with the AI model so it spells them exactly.
          </Legend>
          <Legend term="Exclude">Hides the column from chat entirely.</Legend>
        </dl>
        <div className="overflow-x-auto rounded-md" style={{ border: "1px solid var(--line)" }}>
          <table className="w-full min-w-[1100px] border-collapse text-left text-sm">
            <thead style={{ background: "var(--surface-3)" }}>
              <tr>
                <Th>Header</Th>
                <Th>Identifier</Th>
                <Th>Type</Th>
                <Th>Stats</Th>
                <Th>Description</Th>
                <Th>Value hints</Th>
                <Th className="text-center">Exclude</Th>
              </tr>
            </thead>
            <tbody>
              {data.review.columns.map((c) => (
                <ColumnRow key={c.index} column={c} profile={profileById.get(c.index)} onEdit={column} />
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {report && (
        <section aria-label="Load report" className="rounded-lg p-5" style={CARD_STYLE}>
          <h4 className="text-base font-semibold" style={{ color: "var(--ink)" }}>
            Load report
          </h4>
          <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
            What publishing would load with the settings above. The preview shows the first rows after conversion.
          </p>
          <p data-testid="load-report-counts" className="mt-3 flex flex-wrap gap-2 text-sm">
            <Stat>{report.rows_read.toLocaleString()} rows read</Stat>
            <Stat>{report.rows_to_load.toLocaleString()} to load</Stat>
            <Stat tone={report.rows_rejected > 0 ? "bad" : "neutral"}>
              <span data-testid="rows-rejected">{report.rows_rejected.toLocaleString()}</span> rejected
            </Stat>
          </p>
          {report.rejects.length > 0 && (
            <ul aria-label="Rejected rows" className="mt-3 flex flex-col gap-1 text-sm" style={{ color: "var(--ink)" }}>
              {report.rejects.map((r) => (
                <li key={`${r.row}-${r.column}`}>
                  Row {r.row}: {r.column} — {r.reason === "cast_failed" ? "value does not match the chosen type" : r.reason}
                </li>
              ))}
            </ul>
          )}
          {previewKeys.length > 0 && (
            <div className="mt-4 overflow-x-auto rounded-md" style={{ border: "1px solid var(--line)" }}>
              <table aria-label="Preview" className="w-full border-collapse text-left text-sm">
                <thead style={{ background: "var(--surface-3)" }}>
                  <tr>
                    {previewKeys.map((k) => (
                      <Th key={k} className="font-mono">
                        {k}
                      </Th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {report.preview.map((row, i) => (
                    <tr key={i} style={{ borderTop: "1px solid var(--line)" }}>
                      {previewKeys.map((k) => (
                        <td key={k} className="whitespace-nowrap px-3 py-2" style={{ color: row[k] == null ? "var(--ink-3)" : "var(--ink)" }}>
                          {row[k] === null || row[k] === undefined ? "—" : String(row[k])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {data.schema_diff && (
        <section aria-label="Schema changes" className="rounded-lg p-5 text-sm" style={CARD_STYLE}>
          <h4 className="text-base font-semibold" style={{ color: "var(--ink)" }}>
            Changes from the served version
          </h4>
          <ul className="mt-2 flex flex-col gap-1" style={{ color: "var(--ink)" }}>
            {data.schema_diff.added.map((c) => (
              <li key={`a-${c}`}>Added: {c}</li>
            ))}
            {data.schema_diff.removed.map((c) => (
              <li key={`r-${c}`}>Removed: {c}</li>
            ))}
            {data.schema_diff.retyped.map((c) => (
              <li key={`t-${c.column}`}>
                Retyped: {c.column} ({c.from} → {c.to})
              </li>
            ))}
            {data.schema_diff.renamed.map((c) => (
              <li key={`n-${c.from}`}>
                Renamed: {c.from} → {c.to}
              </li>
            ))}
          </ul>
        </section>
      )}

      {blockers.length > 0 && (
        <section
          aria-label="Publishing is blocked"
          className="rounded-lg p-5 text-sm"
          style={{ border: "1px solid var(--primary-line)", background: "var(--primary-soft)" }}
        >
          <h4 className="text-base font-semibold" style={{ color: "var(--ink)" }}>
            Before you can publish
          </h4>
          <ul className="mt-2 flex list-disc flex-col gap-1 pl-5" style={{ color: "var(--ink)" }}>
            {blockers.map((b) => (
              <li key={`${b.code}-${b.column ?? ""}`}>{(TABULAR_BLOCKER_MESSAGES[b.code] ?? (() => b.code))(b.column)}</li>
            ))}
          </ul>
        </section>
      )}

      {publish.isError && (
        <p role="alert" className="rounded-md px-3 py-2 text-sm" style={{ border: "1px solid var(--primary-line)", background: "var(--primary-soft)", color: "var(--ink)" }}>
          {tabularErrorMessage((publish.error as SafeApiHttpError).code)}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3 border-t pt-5" style={{ borderColor: "var(--line)" }}>
        <button
          type="button"
          disabled={blockers.length > 0 || publish.isPending || review.isPending}
          onClick={() => publish.mutate(undefined, { onSuccess: () => onPublished() })}
          className="rounded-md px-5 py-2 text-sm font-semibold outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-50"
          style={{ background: "var(--primary)", color: "#fff" }}
        >
          {publish.isPending ? "Publishing…" : "Publish"}
        </button>
        <span className="text-xs" style={{ color: "var(--ink-3)" }}>
          {review.isPending ? "Saving your change…" : "Publishing makes this version available to chat."}
        </span>
      </div>
    </div>
  );
}

function orderedPreviewKeys(keys: string[], columns: TabularReviewColumn[]): string[] {
  const position = new Map(columns.map((c) => [c.identifier, c.index]));
  return [...keys].sort((a, b) => (position.get(a) ?? Number.MAX_SAFE_INTEGER) - (position.get(b) ?? Number.MAX_SAFE_INTEGER));
}

function Card({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="rounded-lg p-5" style={CARD_STYLE}>
      <h4 className="text-base font-semibold" style={{ color: "var(--ink)" }}>
        {title}
      </h4>
      {hint && (
        <p className="mt-1 max-w-[75ch] text-sm" style={{ color: "var(--ink-2)" }}>
          {hint}
        </p>
      )}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Legend({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div>
      <dt className="inline font-semibold" style={{ color: "var(--ink)" }}>
        {term}:{" "}
      </dt>
      <dd className="inline">{children}</dd>
    </div>
  );
}

function Th({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <th
      scope="col"
      className={`whitespace-nowrap px-3 py-2.5 text-xs font-semibold uppercase tracking-wide ${className}`}
      style={{ color: "var(--ink-2)" }}
    >
      {children}
    </th>
  );
}

function Stat({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "bad" }) {
  return (
    <span
      className="rounded-full px-3 py-1 text-xs font-medium"
      style={
        tone === "bad"
          ? { background: "var(--primary-soft)", color: "var(--ink)", border: "1px solid var(--primary-line)" }
          : { background: "var(--surface-3)", color: "var(--ink)", border: "1px solid var(--line)" }
      }
    >
      {children}
    </span>
  );
}

function warningText(w: TabularProfileColumn["warnings"][number], chosenType: string): string {
  const rows = (w.rows ?? []).join(", ");
  const where = rows ? ` (rows ${rows})` : "";
  const count = w.count ?? "Some";
  if (w.candidate && w.candidate !== chosenType) {
    return `Kept as ${chosenType}: ${count} value(s) aren't ${w.candidate}, e.g. leading zeros or text${where}.`;
  }
  return `${count} value(s) don't fit ${w.candidate ?? chosenType} and will be rejected${where}.`;
}

function ColumnRow({
  column,
  profile,
  onEdit,
}: {
  column: TabularReviewColumn;
  profile: TabularProfileColumn | undefined;
  onEdit: (edit: TabularColumnEdit) => void;
}) {
  const label = column.label || `column ${column.index + 1}`;
  const muted = column.excluded;
  return (
    <tr className="align-top" style={{ borderTop: "1px solid var(--line)", opacity: muted ? 0.55 : 1 }}>
      <td className="px-3 py-3 font-medium" style={{ color: "var(--ink)" }}>
        {label}
      </td>
      <td className="w-44 px-3 py-3">
        <input
          aria-label={`Identifier for ${label}`}
          defaultValue={column.identifier}
          onBlur={(e) => {
            if (e.target.value !== column.identifier) onEdit({ index: column.index, identifier: e.target.value });
          }}
          className={`${COMPACT_FIELD_CLASS} font-mono`}
          style={FIELD_STYLE}
        />
      </td>
      <td className="w-40 px-3 py-3">
        <div className="flex flex-col gap-2">
          <select
            aria-label={`Type for ${label}`}
            value={column.type}
            onChange={(e) => onEdit({ index: column.index, type: e.target.value as TabularReviewColumn["type"] })}
            className={COMPACT_FIELD_CLASS}
            style={FIELD_STYLE}
          >
            {TABULAR_COLUMN_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          {column.type === "date" && (
            <select
              aria-label={`Date format for ${label}`}
              value={column.date_format ?? ""}
              onChange={(e) => onEdit({ index: column.index, date_format: e.target.value || null })}
              className={COMPACT_FIELD_CLASS}
              style={FIELD_STYLE}
            >
              <option value="">Choose a format</option>
              {TABULAR_DATE_FORMATS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          )}
        </div>
      </td>
      <td className="w-48 px-3 py-3 text-xs leading-5" style={{ color: "var(--ink-2)" }}>
        {profile && (
          <>
            <span className="block">
              {profile.null_count.toLocaleString()} empty · {profile.distinct_count.toLocaleString()} distinct
            </span>
            {profile.warnings.map((w, i) => (
              <span key={i} className="mt-1 block" style={{ color: "var(--ink)" }}>
                {warningText(w, column.type)}
              </span>
            ))}
          </>
        )}
      </td>
      <td className="w-56 px-3 py-3">
        <input
          aria-label={`Description for ${label}`}
          placeholder="What this column means"
          defaultValue={column.description}
          onBlur={(e) => {
            if (e.target.value !== column.description) onEdit({ index: column.index, description: e.target.value });
          }}
          className={COMPACT_FIELD_CLASS}
          style={FIELD_STYLE}
        />
      </td>
      <td className="min-w-[280px] px-3 py-3">
        {column.value_hints.length === 0 ? (
          <span className="text-xs" style={{ color: "var(--ink-3)" }}>
            —
          </span>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {column.value_hints.map((h) => (
              <label
                key={h.value}
                className="inline-flex cursor-pointer items-center gap-1.5 rounded-full px-2.5 py-1 text-xs"
                style={
                  h.approved
                    ? { border: "1px solid var(--primary-line)", background: "var(--primary-soft)", color: "var(--ink)" }
                    : { border: "1px solid var(--line)", background: "var(--surface-3)", color: "var(--ink-2)" }
                }
              >
                <input
                  type="checkbox"
                  checked={h.approved}
                  onChange={(e) => onEdit({ index: column.index, value_hints: [{ value: h.value, approved: e.target.checked }] })}
                  style={{ accentColor: "var(--primary)" }}
                />
                {h.value}
              </label>
            ))}
          </div>
        )}
      </td>
      <td className="px-3 py-3 text-center">
        <input
          type="checkbox"
          aria-label={`Exclude ${label}`}
          checked={column.excluded}
          onChange={(e) => onEdit({ index: column.index, excluded: e.target.checked })}
          style={{ accentColor: "var(--primary)" }}
        />
      </td>
    </tr>
  );
}
