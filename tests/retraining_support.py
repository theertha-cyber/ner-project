"""Fixtures shared by the `human-gated-retraining` test files.

Extends `confidence_review_support` rather than replacing it. The tenant, document, prediction
and review helpers there already build the state this change reads — production-review spans
attributed to a model version — and rebuilding them here would give the two changes separate
ideas of what a reviewed span looks like, which is exactly the drift the consumed-span record
exists to close.

What this module adds is the *training* side of the same tenant: model versions the worker
would actually write (`version_number`, not `002`'s legacy `version`), training jobs in the
states the surfaces care about, and a completion helper that runs the real recording function
against a real connection.

Not a test module — pytest collects `test_*.py`, so this is imported rather than run.
"""

import json
import uuid

from sqlalchemy import text

from tests.confidence_review_support import (  # noqa: F401 — re-exported for the test files
    ORG_END,
    ORG_START,
    add_document,
    add_prediction,
    add_run,
    auth_header,
    drop_test_schemas,
    make_tenant,
)


async def add_model_version(
    engine,
    tenant,
    version_number: int,
    *,
    status: str = "completed",
    metrics: dict | None = None,
    training_job_id: str | None = None,
):
    """One `model_versions` row shaped the way the training worker writes them.

    `version_number` is populated and `version` is left NULL, which is what the worker has done
    since `018`. A helper that filled `version` instead would let these tests pass against a
    reader that only the fixtures could satisfy.
    """
    version_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {tenant['schema']}.model_versions "
                "(id, tenant_id, version_number, status, metrics, training_job_id, "
                " artifact_path, active_flag) "
                "VALUES (:id, :tid, :vn, :status, CAST(:metrics AS jsonb), :job, :path, :active)"
            ),
            {
                "id": version_id,
                "tid": tenant["tid"],
                "vn": version_number,
                "status": status,
                "metrics": json.dumps(metrics) if metrics is not None else None,
                "job": training_job_id,
                "path": f"tenants/{tenant['tid']}/models/v{version_number}/",
                "active": status == "promoted",
            },
        )
    return version_id


async def ensure_audit_events(engine):
    """The `public.audit_events` table the approval flow writes to.

    Needed by any test that drives approve or reject through `training_service`, because those
    endpoints record an audit event and a missing table would fail the request for a reason that
    has nothing to do with what the test is checking. Created here rather than mocked away: the
    tests that reject a job are asserting the *real* approval path records no consumed spans, and
    a path with its audit write stubbed out is not that path.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.audit_events (
                    id VARCHAR PRIMARY KEY,
                    actor VARCHAR,
                    role VARCHAR,
                    action VARCHAR,
                    target VARCHAR,
                    kind VARCHAR,
                    tenant_id VARCHAR,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
        )


async def add_training_job(engine, tenant, *, status: str = "pending_approval", job_id=None):
    job_id = job_id or str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {tenant['schema']}.training_jobs "
                "(id, tenant_id, status, run_number) VALUES (:id, :tid, :status, 1)"
            ),
            {"id": job_id, "tid": tenant["tid"], "status": status},
        )
    return job_id


async def review_spans(client_factory, engine, tenant, doc_id, run_id, count, *,
                       entity_type="organization", model_version="3", base_model=False):
    """`count` production-review spans, created the way review actually creates them.

    Resolved through the review endpoint rather than inserted, so a span here has whatever shape
    the resolution path produces. Inserting spans and provenance rows by hand would let this
    file agree with itself about a shape the endpoint might not write — change 5's own
    accumulation tests take the same care for the same reason.
    """
    span_ids = []
    for _ in range(count):
        pred_id = await add_prediction(
            engine,
            tenant,
            run_id,
            doc_id,
            entity_type=entity_type,
            char_start=ORG_START,
            char_end=ORG_END,
            model_version=model_version,
            served_by_base_model=base_model,
        )
        async with client_factory() as client:
            resp = await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "confirmed"},
                headers=auth_header(tenant["tid"]),
            )
        assert resp.status_code == 200, resp.text
        span_ids.append(resp.json()["span_id"])
    return span_ids


async def dataset_span_ids_now(engine, tenant) -> list[str]:
    """The span set a training run started right now would consume.

    Calls the production SQL builder rather than restating the query, so a test that asserts a
    run consumed "the dataset" is asserting about the same statement the worker runs.
    """
    from src.training_service.services.consumed_spans import dataset_span_ids_sql

    async with engine.begin() as conn:
        result = await conn.execute(text(dataset_span_ids_sql(tenant["schema"])))
        return [str(row[0]) for row in result.fetchall()]


async def complete_run(engine, tenant, span_ids, version_number, job_id=None):
    """Record `span_ids` as consumed by `version_number`, through the production writer.

    This is the worker's completion step with the training removed: the same function, the same
    SQL, the same arguments. Calling it directly rather than running `fine_tune_model` is what
    lets these tests assert about the recording without a GPU, a model download, or MLflow — and
    the separation is why `record_consumed_spans` is a module rather than an inline block.
    """
    from src.training_service.services.consumed_spans import record_sql

    statement = text(record_sql(tenant["schema"]))
    async with engine.begin() as conn:
        for span_id in span_ids:
            await conn.execute(
                statement,
                {
                    "span_id": str(span_id),
                    "model_version": str(version_number),
                    "training_job_id": job_id,
                },
            )


async def consumed_rows(engine, tenant) -> list[tuple[str, str]]:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                f"SELECT span_id, model_version FROM {tenant['schema']}.span_training_consumption"
            )
        )
        return [(str(r[0]), str(r[1])) for r in result.fetchall()]
