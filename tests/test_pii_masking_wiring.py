"""End-to-end wiring: `extract_and_ground_document` actually masks before calling the external
LLM, translates its offsets back, merges with local detections, and fails closed.

Real database (tenant isolation and storage are exactly what a mock would hide), stubbed
external LLM (`StubLLMClient`) and stubbed local model (`StubLocalModelClient`) — the two
providers tests must never reach for real.

Covers the `automated-annotation-pii-masking` change's Extraction Scope, Grounding and
Verification, Suggested Span Storage, Safe-Copy Generation, Local-Only Type Coverage
Requirement, and Fail-Closed requirements at the wiring level (unit coverage for the mechanism
itself lives in `test_pii_masking.py`).
"""

import uuid

import pytest
from sqlalchemy import text

from src.annotation_service.services.llm_client import StubLLMClient
from src.annotation_service.services.pii_masking import (
    LocalDetectionUnavailable,
    StubLocalModelClient,
)
from src.annotation_service.worker import run_llm_prelabel_sync
from tests.test_llm_prelabel_api import (  # noqa: F401 — fixtures are used by name
    _add_document,
    _make_tenant,
    auth_header,
    client,
    cleanup,
    engine,
    fake_send_task,
    make_token,
)

DOCUMENT_TEXT = (
    "Jimmy Smith is listed. Case number 123-45-6789 on file. "
    "Acme Corp handles billing."
)


async def _make_masking_tenant(engine, *, local_only_mapped: bool = True):
    """A tenant with one of each sensitivity: `organization` (open), `case_number` (pattern,
    with a validation_rule), and `child_name` (local_only, with or without a base_label_mapping,
    per the coverage-requirement tests)."""
    tenant = await _make_tenant(engine, entity_types=False)
    schema = tenant["schema"]
    mapping = '{"PER": ["child_name"]}' if local_only_mapped else "{}"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.entity_definitions "
                "(id, tenant_id, name, description, examples, version, is_active, sensitivity, "
                " validation_rule, base_label_mapping) VALUES "
                "(:i1, :tid, 'organization', 'A company', '[]', 1, true, 'open', NULL, NULL), "
                "(:i2, :tid, 'case_number', 'A case number', '[]', 1, true, 'pattern', "
                "   '\\d{3}-\\d{2}-\\d{4}', NULL), "
                "(:i3, :tid, 'child_name', 'A child''s name', '[]', 1, true, 'local_only', "
                "   NULL, CAST(:mapping AS JSON))"
            ),
            {
                "i1": str(uuid.uuid4()), "i2": str(uuid.uuid4()), "i3": str(uuid.uuid4()),
                "tid": tenant["tid"], "mapping": mapping,
            },
        )
    return tenant


def _local_model_stub() -> StubLocalModelClient:
    """Predicts "Jimmy Smith" as PER at word indices 0-1 of the document's whitespace tokens
    (`Jimmy Smith is listed. Case number 123-45-6789 on file. Acme Corp handles billing.`)."""
    return StubLocalModelClient(
        predictions=[
            {"token": "Jimmy", "label": "B-PER", "confidence": 0.95, "word_index": 0},
            {"token": "Smith", "label": "I-PER", "confidence": 0.95, "word_index": 1},
        ]
    )


def _llm_response_for(quote: str) -> dict:
    return {"entities": [{"entity_type": "organization", "quote": quote}]}


class TestExternalPayloadExcludesSensitiveTypes:
    async def test_prompt_names_only_the_open_type(self, engine):
        tenant = await _make_masking_tenant(engine)
        doc_id = await _add_document(engine, tenant, document_text=DOCUMENT_TEXT)
        job_id = str(uuid.uuid4())
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"INSERT INTO {tenant['schema']}.llm_prelabel_jobs "
                    "(id, document_id, status, content_hash, config_version) "
                    "VALUES (:id, :doc_id, 'queued', 'x', 'x')"
                ),
                {"id": job_id, "doc_id": doc_id},
            )

        llm_client = StubLLMClient(_llm_response_for("Acme Corp"))
        run_llm_prelabel_sync(
            tenant["tid"], doc_id, job_id,
            llm_client=llm_client, local_model_client=_local_model_stub(),
        )

        assert "- organization" in llm_client.last_payload
        assert "- case_number" not in llm_client.last_payload
        assert "- child_name" not in llm_client.last_payload

    async def test_prompt_never_contains_the_real_sensitive_text(self, engine):
        tenant = await _make_masking_tenant(engine)
        doc_id = await _add_document(engine, tenant, document_text=DOCUMENT_TEXT)
        job_id = str(uuid.uuid4())
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"INSERT INTO {tenant['schema']}.llm_prelabel_jobs "
                    "(id, document_id, status, content_hash, config_version) "
                    "VALUES (:id, :doc_id, 'queued', 'x', 'x')"
                ),
                {"id": job_id, "doc_id": doc_id},
            )

        llm_client = StubLLMClient(_llm_response_for("Acme Corp"))
        run_llm_prelabel_sync(
            tenant["tid"], doc_id, job_id,
            llm_client=llm_client, local_model_client=_local_model_stub(),
        )

        assert "Jimmy Smith" not in llm_client.last_payload
        assert "123-45-6789" not in llm_client.last_payload
        assert "Acme Corp" in llm_client.last_payload


class TestMergedStorageAndOffsetTranslation:
    async def test_all_three_sources_are_stored_with_real_text_and_correct_offsets(self, engine):
        tenant = await _make_masking_tenant(engine)
        doc_id = await _add_document(engine, tenant, document_text=DOCUMENT_TEXT)
        schema = tenant["schema"]
        job_id = str(uuid.uuid4())
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.llm_prelabel_jobs "
                    "(id, document_id, status, content_hash, config_version) "
                    "VALUES (:id, :doc_id, 'queued', 'x', 'x')"
                ),
                {"id": job_id, "doc_id": doc_id},
            )

        run_llm_prelabel_sync(
            tenant["tid"], doc_id, job_id,
            llm_client=StubLLMClient(_llm_response_for("Acme Corp")),
            local_model_client=_local_model_stub(),
        )

        async with engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        f"SELECT entity_type, char_start, char_end, text_content, source "
                        f"FROM {schema}.suggested_spans WHERE document_id = :doc_id"
                    ),
                    {"doc_id": doc_id},
                )
            ).fetchall()

        by_type = {row[0]: row for row in rows}
        assert set(by_type) == {"child_name", "case_number", "organization"}

        child = by_type["child_name"]
        assert child[3] == "Jimmy Smith"
        assert child[4] == "local_model"
        assert DOCUMENT_TEXT[child[1]:child[2]] == "Jimmy Smith"

        case = by_type["case_number"]
        assert case[3] == "123-45-6789"
        assert case[4] == "pattern"
        assert DOCUMENT_TEXT[case[1]:case[2]] == "123-45-6789"

        org = by_type["organization"]
        assert org[3] == "Acme Corp"
        assert org[4] == "llm"
        # The proof that translation worked: the LLM only ever saw the masked copy (where
        # "Jimmy Smith" and "123-45-6789" are placeholders of different lengths), yet this
        # offset is correct against the *original* document.
        assert DOCUMENT_TEXT[org[1]:org[2]] == "Acme Corp"
        assert org[1] == DOCUMENT_TEXT.index("Acme Corp")


class TestFailClosed:
    async def test_local_model_failure_blocks_the_external_call(self, engine):
        tenant = await _make_masking_tenant(engine)
        doc_id = await _add_document(engine, tenant, document_text=DOCUMENT_TEXT)
        schema = tenant["schema"]
        job_id = str(uuid.uuid4())
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.llm_prelabel_jobs "
                    "(id, document_id, status, content_hash, config_version) "
                    "VALUES (:id, :doc_id, 'queued', 'x', 'x')"
                ),
                {"id": job_id, "doc_id": doc_id},
            )

        llm_client = StubLLMClient(_llm_response_for("Acme Corp"))
        with pytest.raises(LocalDetectionUnavailable):
            run_llm_prelabel_sync(
                tenant["tid"], doc_id, job_id,
                llm_client=llm_client,
                local_model_client=StubLocalModelClient(fail=True),
            )

        assert llm_client.call_count == 0

        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        f"SELECT status, error_message FROM {schema}.llm_prelabel_jobs "
                        "WHERE id = :id"
                    ),
                    {"id": job_id},
                )
            ).fetchone()
        assert row[0] == "failed"
        assert row[1].startswith("local detection failed:")


async def _trigger_and_run(client, tenant, doc_id, llm_client, local_model_client):
    """One full cycle: trigger, and run the task only if the trigger actually enqueued one —
    mirroring `test_llm_prelabel_cache.py`'s own `_trigger_and_run`, extended with a local model
    client so a tenant carrying `local_only`/`pattern` types never makes a real network call."""
    resp = await client.post(
        f"/api/v1/documents/{doc_id}/prelabel/llm",
        headers=auth_header(make_token(tenant["tid"])),
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    if not body["cached"]:
        run_llm_prelabel_sync(
            tenant["tid"], doc_id, body["job_id"],
            llm_client=llm_client, local_model_client=local_model_client,
        )
    return body


class TestCacheBustsOnMaskingConfigChange:
    """The correctness fix made during implementation: `CONFIG_FIELDS` must include
    `sensitivity`, `validation_rule`, and `base_label_mapping`, not just the four fields the
    external prompt reads — each of these three governs *local* detection instead, and a stale
    cache entry would otherwise keep serving pre-reclassification behavior indefinitely."""

    async def test_reclassifying_sensitivity_invalidates_the_cache(self, client, engine):
        tenant = await _make_masking_tenant(engine)
        doc_id = await _add_document(engine, tenant, document_text=DOCUMENT_TEXT)
        llm_client = StubLLMClient(_llm_response_for("Acme Corp"))

        first = await _trigger_and_run(
            client, tenant, doc_id, llm_client, _local_model_stub()
        )
        assert first["cached"] is False
        assert llm_client.call_count == 1

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE public.entity_definitions SET sensitivity = 'open', "
                    "version = version + 1 WHERE tenant_id = :tid AND name = 'child_name'"
                ),
                {"tid": tenant["tid"]},
            )

        second = await _trigger_and_run(
            client, tenant, doc_id, llm_client, _local_model_stub()
        )
        assert second["cached"] is False
        assert llm_client.call_count == 2
        # `child_name` is `open` now, so the external prompt should name it.
        assert "- child_name" in llm_client.last_payload

    async def test_changing_a_validation_rule_invalidates_the_cache(self, client, engine):
        tenant = await _make_masking_tenant(engine)
        doc_id = await _add_document(engine, tenant, document_text=DOCUMENT_TEXT)
        llm_client = StubLLMClient(_llm_response_for("Acme Corp"))

        first = await _trigger_and_run(
            client, tenant, doc_id, llm_client, _local_model_stub()
        )
        assert first["cached"] is False

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE public.entity_definitions SET validation_rule = :rule, "
                    "version = version + 1 WHERE tenant_id = :tid AND name = 'case_number'"
                ),
                {"tid": tenant["tid"], "rule": r"\d{4}-\d{2}-\d{4}"},
            )

        second = await _trigger_and_run(
            client, tenant, doc_id, llm_client, _local_model_stub()
        )
        assert second["cached"] is False
        assert llm_client.call_count == 2


class TestLocalOnlyCoverageRequirement:
    async def test_trigger_refused_when_local_only_type_has_no_mapping(self, client, engine):
        tenant = await _make_masking_tenant(engine, local_only_mapped=False)
        doc_id = await _add_document(engine, tenant, document_text=DOCUMENT_TEXT)

        resp = await client.post(
            f"/api/v1/documents/{doc_id}/prelabel/llm",
            headers=auth_header(make_token(tenant["tid"])),
        )

        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "LOCAL_ONLY_TYPE_NOT_COVERED"

    async def test_trigger_allowed_when_local_only_type_is_mapped(self, client, engine, fake_send_task):
        tenant = await _make_masking_tenant(engine, local_only_mapped=True)
        doc_id = await _add_document(engine, tenant, document_text=DOCUMENT_TEXT)

        resp = await client.post(
            f"/api/v1/documents/{doc_id}/prelabel/llm",
            headers=auth_header(make_token(tenant["tid"])),
        )

        assert resp.status_code == 202
