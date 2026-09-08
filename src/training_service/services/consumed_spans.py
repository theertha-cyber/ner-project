"""What a training run consumed, recorded when the run finishes.

This is the writer for `{schema}.span_training_consumption`, the table migration `040` created
and left empty. Change 5 defines that table and reads it — accumulation is *spans no run has
consumed yet* — and says in as many words that change 6 owns the writer. Without this module the
accumulation figure is a delta against a version that nothing ever advances: correct once, wrong
after the first retrain, and wrong silently.

**Two moments, deliberately separated.**

`dataset_span_ids` runs where the dataset is built. `record_consumed_spans` runs where the run
succeeds. They are not the same moment and must not be collapsed into one:

* Capturing the set at dataset-build time is what makes the record *true*. The run trains on the
  spans that existed when the export was taken; spans created while it trains were not in the
  dataset, and counting them as consumed would zero accumulation for evidence the model never
  saw.
* Writing at completion is what makes the record *earned*. A job rejected at approval, or one
  that fails partway, consumed nothing — no model came out of it — so recording consumption for
  either would zero the figure while leaving the tenant exactly where they started, and destroy
  the evidence that the retrain never happened (design.md Decision 1, verification.md Risk 2).

Nothing here creates, enqueues, or schedules a training job, and nothing here promotes a model
version. Recording what a run consumed is bookkeeping about a run that already finished; it is
not a signal to start another one (design.md Decision 3).

**The span set.** `_DATASET_SPAN_IDS_SQL` mirrors what `annotation_service`'s
`/api/v1/annotation-export` actually exports: every span on a document that has text, with no
entity-type filter, because the worker requests the export without one. Imported annotations are
exported too but have no span rows, so there is nothing to record for them — they are not
production-review evidence and do not enter the accumulation figure either.

Tenant scoping is by schema, the way every other statement in this service resolves it
(ADR-001), and the recorded version is the version the run *produced*, not the version that
predicted the spans (ADR-003).
"""

from sqlalchemy import text

# Spans the export would have covered. `EXISTS` against `document_text_spans` rather than a join,
# so a document stored as several text spans contributes each of its spans once rather than once
# per text row.
_DATASET_SPAN_IDS_SQL = """
    SELECT sp.id
    FROM {schema}.spans sp
    WHERE EXISTS (
        SELECT 1 FROM {schema}.document_text_spans dts
        WHERE dts.document_id = sp.document_id
    )
"""

# `ON CONFLICT DO NOTHING` because `span_id` is the primary key and a span consumed by one run is
# consumed by every later run over the same corpus. The first run to consume it is the one that
# matters: the figure asks "has any run trained on this yet?", and the answer stops being no the
# first time. Without this, a second run would raise and fail a job that had already succeeded.
_RECORD_SQL = """
    INSERT INTO {schema}.span_training_consumption (span_id, model_version, training_job_id)
    VALUES (:span_id, :model_version, :training_job_id)
    ON CONFLICT (span_id) DO NOTHING
"""


def dataset_span_ids_sql(schema: str) -> str:
    return _DATASET_SPAN_IDS_SQL.format(schema=schema)


def record_sql(schema: str) -> str:
    return _RECORD_SQL.format(schema=schema)


def dataset_span_ids(conn, schema: str) -> list[str]:
    """The span ids the dataset just built from this tenant covers.

    Called at dataset-build time and carried in memory until the run completes. Re-querying at
    completion instead would sweep in spans reviewed *during* the run and record them as trained
    on when they were not.
    """
    rows = conn.execute(text(dataset_span_ids_sql(schema))).fetchall()
    return [str(row[0]) for row in rows]


def record_consumed_spans(
    conn,
    schema: str,
    span_ids,
    model_version,
    training_job_id: str | None = None,
) -> int:
    """Record `span_ids` as consumed by `model_version`. Returns how many ids were offered.

    Caller supplies the connection so this participates in whatever transaction the completion
    path is already in — the record and the run's own completion either both land or neither
    does. A half-recorded set would leave accumulation reporting a figure that matches no run.
    """
    ids = [str(span_id) for span_id in span_ids]
    if not ids:
        return 0
    statement = text(record_sql(schema))
    version = str(model_version)
    for span_id in ids:
        conn.execute(
            statement,
            {
                "span_id": span_id,
                "model_version": version,
                "training_job_id": training_job_id,
            },
        )
    return len(ids)
