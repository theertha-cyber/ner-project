"""The extraction worker writes EAV and relational rows in one transaction, or neither.

The pure builders are covered without a database in `test_relational_projection_generator.py`.
What is left here is everything only a real transaction can settle: that both stores commit
together, that a failure leaves neither behind, that re-extraction replaces rather than
appends, and that reconciliation happens once per run rather than once per document.

Covers verification.md rows 1, 2, 5, 13, 14, 15, 22, 23, 24, 25, 26, 27, 31, 79-84.
"""

import os
import uuid

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_MODEL_SERVING_URL", "http://test-model-serving:8004")

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text

from src.extraction_service import worker as worker_module
from src.extraction_service.services.entity_store import _schema
from src.shared.config import settings

pytestmark = pytest.mark.asyncio


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


_TENANT_TABLES = [
    """
    CREATE TABLE "{schema}".documents (
        id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, filename VARCHAR(255) NOT NULL,
        status VARCHAR(20) DEFAULT 'processed',
        purpose VARCHAR(20) NOT NULL DEFAULT 'query'
    )
    """,
    """
    CREATE TABLE "{schema}".document_text_spans (
        id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, span_index INTEGER,
        text TEXT, char_start INTEGER, page_number INTEGER
    )
    """,
    """
    CREATE TABLE "{schema}".extraction_runs (
        id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, document_id VARCHAR,
        model_version VARCHAR, status VARCHAR NOT NULL DEFAULT 'queued',
        started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        completed_at TIMESTAMP WITH TIME ZONE, total_documents INTEGER NOT NULL DEFAULT 0,
        processed_count INTEGER NOT NULL DEFAULT 0, skipped_count INTEGER NOT NULL DEFAULT 0,
        processing_mode VARCHAR(32) NOT NULL DEFAULT 'bert_only',
        postprocess_model TEXT, postprocess_prompt_version TEXT,
        postprocess_degraded BOOLEAN NOT NULL DEFAULT FALSE,
        failed_count INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE "{schema}".model_versions (
        tenant_id VARCHAR, version INTEGER, version_number INTEGER, status VARCHAR
    )
    """,
    """
    CREATE TABLE "{schema}".extracted_entities (
        id VARCHAR PRIMARY KEY, run_id VARCHAR, document_id VARCHAR, entity_id VARCHAR,
        value TEXT, confidence FLOAT, review_status VARCHAR DEFAULT 'unreviewed'
    )
    """,
    """
    CREATE TABLE "{schema}".document_entities (
        id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, entity_type TEXT NOT NULL,
        entity_value TEXT NOT NULL, normalized_value TEXT NOT NULL,
        confidence DOUBLE PRECISION NOT NULL,
        page_number INTEGER, char_start INTEGER, char_end INTEGER,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        value_kind TEXT, value_number DOUBLE PRECISION, value_number_high DOUBLE PRECISION,
        value_unit TEXT, value_date DATE, value_date_high DATE,
        source_entity_value TEXT, source_entity_type TEXT,
        postprocess_status TEXT NOT NULL DEFAULT 'not_applied',
        postprocess_model TEXT, postprocess_prompt_version TEXT,
        postprocess_at TIMESTAMPTZ,
        extraction_schema_version INTEGER NOT NULL DEFAULT 1,
        occurrence_count INTEGER NOT NULL DEFAULT 1
    )
    """,
]


class Tenant:
    """A tenant schema plus the handful of helpers every test below needs."""

    def __init__(self, tenant_id, sync_engine):
        self.tenant_id = tenant_id
        self.schema = _schema(tenant_id)
        self.engine = sync_engine

    def add_document(self, doc_id, filename="cv.pdf", text_body="Arjun works at InApp"):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f'INSERT INTO "{self.schema}".documents (id, tenant_id, filename, status) '
                    "VALUES (:id, :tid, :fn, 'processed')"
                ),
                {"id": doc_id, "tid": self.tenant_id, "fn": filename},
            )
            conn.execute(
                text(
                    f'INSERT INTO "{self.schema}".document_text_spans '
                    "(id, document_id, span_index, text, char_start, page_number) "
                    "VALUES (:id, :doc, 0, :body, 0, 1)"
                ),
                {"id": f"span-{doc_id}", "doc": doc_id, "body": text_body},
            )

    def define(self, name, identifier, cardinality="multi", **columns):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO public.entity_definitions "
                    "(id, tenant_id, name, sql_identifier, cardinality, value_kind, is_active, "
                    " base_label_mapping, version) "
                    "VALUES (:id, :tid, :name, :identifier, :cardinality, :kind, :active, "
                    "        :mapping, 1)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tid": self.tenant_id,
                    "name": name,
                    "identifier": identifier,
                    "cardinality": cardinality,
                    "kind": columns.get("value_kind"),
                    "active": columns.get("is_active", True),
                    "mapping": columns.get("base_label_mapping"),
                },
            )

    def deactivate(self, name):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE public.entity_definitions SET is_active = false "
                    "WHERE tenant_id = :tid AND name = :name"
                ),
                {"tid": self.tenant_id, "name": name},
            )

    def rows(self, sql, **params):
        with self.engine.begin() as conn:
            return [tuple(r) for r in conn.execute(text(sql.format(s=self.schema)), params)]

    def count(self, table, doc_id=None):
        clause = " WHERE document_id = :doc" if doc_id else ""
        return self.rows(
            f'SELECT count(*) FROM "{{s}}".{table}{clause}', **({"doc": doc_id} if doc_id else {})
        )[0][0]

    def run(self, run_id, doc_ids):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f'INSERT INTO "{self.schema}".extraction_runs (id, tenant_id, status) '
                    "VALUES (:id, :tid, 'queued') ON CONFLICT (id) DO NOTHING"
                ),
                {"id": run_id, "tid": self.tenant_id},
            )
        worker_module.run_batch_extraction.run(self.tenant_id, run_id, doc_ids)
        return self.rows(
            'SELECT status, processed_count, failed_count FROM "{s}".extraction_runs '
            "WHERE id = :id",
            id=run_id,
        )[0]


@pytest_asyncio.fixture
async def tenant(monkeypatch, engine, setup_database):
    tid = f"proj-{uuid.uuid4().hex[:8]}"
    schema = _schema(tid)
    sync_engine = create_engine(settings.database_url_sync)

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, "
                "max_storage_gb, max_model_versions) "
                "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tid},
        )
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    with sync_engine.begin() as conn:
        for ddl in _TENANT_TABLES:
            conn.execute(text(ddl.format(schema=schema)))

    monkeypatch.setattr(worker_module, "_get_sync_engine", lambda: sync_engine)
    monkeypatch.setattr(worker_module, "_get_active_model_version", lambda tenant_id: "1")

    import src.shared.auth as auth_module

    monkeypatch.setattr(auth_module, "create_access_token", lambda **kwargs: "fake-token")

    yield Tenant(tid, sync_engine)

    with sync_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.entity_definitions WHERE tenant_id = :tid"), {"tid": tid}
        )
    async with engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
    sync_engine.dispose()


def _predict(monkeypatch, predictions, model_version="1"):
    def mock_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse({"predictions": predictions, "model_version": model_version})

    monkeypatch.setattr(worker_module.requests, "post", mock_post)


_PER_ORG = [
    {"token": "Arjun", "label": "B-PER", "confidence": 0.95},
    {"token": "works", "label": "O", "confidence": 0.5},
    {"token": "at", "label": "O", "confidence": 0.5},
    {"token": "InApp", "label": "B-ORG", "confidence": 0.85},
]


class TestBothStoresCommitTogether:
    """verification.md rows 1, 14, 15, 22, 81"""

    async def test_eav_and_relational_reflect_the_same_entities(self, tenant, monkeypatch):
        tenant.define("PER", "e_per")
        tenant.define("ORG", "e_org")
        tenant.add_document("doc-1", filename="arjun.pdf")
        _predict(monkeypatch, _PER_ORG)

        status, processed, failed = tenant.run("run-1", ["doc-1"])
        assert (status, processed, failed) == ("completed", 1, 0)

        eav = tenant.rows(
            'SELECT entity_type, entity_value FROM "{s}".document_entities '
            "WHERE document_id = 'doc-1' ORDER BY entity_type"
        )
        assert eav == [("ORG", "InApp"), ("PER", "Arjun")]

        assert tenant.rows(
            'SELECT value, confidence FROM "{s}".e_per WHERE document_id = \'doc-1\''
        ) == [("Arjun", 0.95)]
        assert tenant.rows(
            'SELECT value FROM "{s}".e_org WHERE document_id = \'doc-1\''
        ) == [("InApp",)]

    async def test_every_processed_document_gets_a_subject_row_with_its_filename(
        self, tenant, monkeypatch
    ):
        tenant.define("PER", "e_per")
        tenant.add_document("doc-1", filename="arjun.pdf")
        _predict(monkeypatch, _PER_ORG)

        tenant.run("run-1", ["doc-1"])
        assert tenant.rows(
            'SELECT document_id, filename FROM "{s}".subject'
        ) == [("doc-1", "arjun.pdf")]

    async def test_a_zero_entity_document_still_gets_a_subject_row(self, tenant, monkeypatch):
        # Without the row, "documents where nothing was found" is unanswerable and every
        # LEFT JOIN in generated SQL silently under-counts the corpus.
        tenant.define("PER", "e_per")
        tenant.add_document("doc-empty", filename="blank.pdf")
        _predict(monkeypatch, [{"token": "Arjun", "label": "O", "confidence": 0.5}])

        status, processed, failed = tenant.run("run-1", ["doc-empty"])
        assert (status, processed, failed) == ("completed", 1, 0)
        assert tenant.count("document_entities", "doc-empty") == 0
        assert tenant.rows(
            'SELECT document_id, filename FROM "{s}".subject'
        ) == [("doc-empty", "blank.pdf")]

    async def test_a_single_definition_lands_on_subject_not_in_a_child_table(
        self, tenant, monkeypatch
    ):
        tenant.define("PER", "e_per", cardinality="single")
        tenant.add_document("doc-1")
        _predict(monkeypatch, _PER_ORG)

        tenant.run("run-1", ["doc-1"])
        assert tenant.rows('SELECT per FROM "{s}".subject') == [("Arjun",)]
        assert "e_per" not in {
            r[0] for r in tenant.rows("SELECT tablename FROM pg_tables WHERE schemaname = '{s}'")
        }


class TestRoutingThroughTheWorker:
    """verification.md rows 13, 24"""

    async def test_a_base_model_label_reaches_the_tenants_own_table(self, tenant, monkeypatch):
        # ADR-008: the shared base model is the default, and it emits CoNLL labels rather than
        # the tenant's entity names. Name-equality routing would leave this table empty.
        tenant.define("Employer", "e_employer", base_label_mapping='{"ORG": ["employer"]}')
        tenant.add_document("doc-1")
        _predict(monkeypatch, _PER_ORG)

        tenant.run("run-1", ["doc-1"])
        assert tenant.rows('SELECT value FROM "{s}".e_employer') == [("InApp",)]

    async def test_an_unroutable_entity_reaches_eav_only_and_does_not_fail_the_document(
        self, tenant, monkeypatch
    ):
        tenant.define("PER", "e_per")
        tenant.add_document("doc-1")
        _predict(monkeypatch, _PER_ORG)

        status, processed, failed = tenant.run("run-1", ["doc-1"])
        assert (status, processed, failed) == ("completed", 1, 0)
        # ORG has no definition at all; the EAV store's tolerance for undefined types is
        # deliberate and must survive the projection.
        assert ("ORG", "InApp") in tenant.rows(
            'SELECT entity_type, entity_value FROM "{s}".document_entities'
        )
        assert tenant.count("e_per", "doc-1") == 1

    async def test_two_labels_collapsing_onto_one_definition_do_not_raise(
        self, tenant, monkeypatch
    ):
        tenant.define(
            "Anything", "e_anything", base_label_mapping='{"PER": ["x"], "ORG": ["x"]}'
        )
        tenant.add_document("doc-1")
        # Both predictions reconstruct to the same normalized value, so both route to the same
        # definition and collide on its primary key. `ON CONFLICT` is what keeps that from
        # failing a document over a catalog choice.
        _predict(
            monkeypatch,
            [
                {"token": "InApp", "label": "B-PER", "confidence": 0.6},
                {"token": "InApp", "label": "B-ORG", "confidence": 0.9},
            ],
        )

        status, processed, failed = tenant.run("run-1", ["doc-1"])
        assert (status, processed, failed) == ("completed", 1, 0)
        rows = tenant.rows('SELECT normalized_value, confidence FROM "{s}".e_anything')
        assert len(rows) == 1
        assert rows[0][1] == 0.9


class TestFullReplaceOnReExtraction:
    """verification.md rows 25, 26, 27, 83"""

    async def test_a_new_model_version_replaces_rather_than_appends(self, tenant, monkeypatch):
        tenant.define("PER", "e_per")
        tenant.add_document("doc-1")
        _predict(monkeypatch, _PER_ORG)
        tenant.run("run-1", ["doc-1"])

        eav_before = tenant.count("document_entities", "doc-1")
        child_before = tenant.count("e_per", "doc-1")
        ledger_before = tenant.count("extracted_entities", "doc-1")

        # A new model version legitimately makes the document eligible again — the supported
        # "add entity type -> retrain -> re-run" workflow.
        monkeypatch.setattr(worker_module, "_get_active_model_version", lambda tenant_id: "2")
        _predict(monkeypatch, _PER_ORG, model_version="2")
        tenant.run("run-2", ["doc-1"])

        assert tenant.count("document_entities", "doc-1") == eav_before
        assert tenant.count("e_per", "doc-1") == child_before
        assert tenant.count("subject") == 1
        # `extracted_entities` is the idempotency ledger and per-run audit: it grows.
        assert tenant.count("extracted_entities", "doc-1") == ledger_before * 2

    async def test_same_model_version_is_still_skipped(self, tenant, monkeypatch):
        tenant.define("PER", "e_per")
        tenant.add_document("doc-1")
        _predict(monkeypatch, _PER_ORG)
        tenant.run("run-1", ["doc-1"])

        status, processed, failed = tenant.run("run-2", ["doc-1"])
        # The eligibility check is unchanged by this change; the path that matters is a new
        # model version, not a repeated run of the same one.
        assert (status, processed, failed) == ("completed", 0, 0)
        assert tenant.count("e_per", "doc-1") == 1

    async def test_a_deactivated_definitions_stale_rows_are_cleared(self, tenant, monkeypatch):
        tenant.define("PER", "e_per")
        tenant.add_document("doc-1")
        _predict(monkeypatch, _PER_ORG)
        tenant.run("run-1", ["doc-1"])
        assert tenant.count("e_per", "doc-1") == 1

        tenant.deactivate("PER")
        monkeypatch.setattr(worker_module, "_get_active_model_version", lambda tenant_id: "2")
        _predict(monkeypatch, _PER_ORG, model_version="2")
        tenant.run("run-2", ["doc-1"])

        # The table survives — nothing is ever dropped — but its rows for this document do not,
        # or reactivation would put the previous generation back on the query surface.
        assert "e_per" in {
            r[0] for r in tenant.rows("SELECT tablename FROM pg_tables WHERE schemaname = '{s}'")
        }
        assert tenant.count("e_per", "doc-1") == 0


class TestFailureIsolation:
    """verification.md rows 2, 31"""

    async def test_a_missing_generated_table_fails_the_document_and_the_run_continues(
        self, tenant, monkeypatch
    ):
        tenant.define("PER", "e_per")
        tenant.add_document("doc-1", filename="a.pdf")
        tenant.add_document("doc-2", filename="b.pdf")
        _predict(monkeypatch, _PER_ORG)

        # Reconciliation would create the table, so it is dropped out of band immediately
        # afterwards — exactly the "catalog and schema genuinely disagree" condition.
        real_reconcile = worker_module.reconcile_entity_tables_sync
        first_doc = "doc-1"

        def reconcile_then_drop(conn, schema, definitions):
            statements = real_reconcile(conn, schema, definitions)
            conn.execute(text(f'DROP TABLE IF EXISTS "{schema}".e_per'))
            return statements

        monkeypatch.setattr(worker_module, "reconcile_entity_tables_sync", reconcile_then_drop)

        status, processed, failed = tenant.run("run-1", [first_doc, "doc-2"])

        assert status == "completed"
        assert processed == 0 and failed == 2
        # Nothing of the failed documents survives in either store.
        assert tenant.count("document_entities") == 0
        assert tenant.count("extracted_entities") == 0
        assert tenant.count("subject") == 0

    async def test_a_failed_document_does_not_stop_the_run(self, tenant, monkeypatch):
        tenant.define("PER", "e_per")
        tenant.add_document("doc-good", filename="a.pdf")
        tenant.add_document("doc-bad", filename="b.pdf")
        _predict(monkeypatch, _PER_ORG)

        real_project = worker_module.project_document_entities

        def project_or_raise(conn, schema, document_id, filename, entities, specs):
            if document_id == "doc-bad":
                raise RuntimeError("projection blew up")
            return real_project(conn, schema, document_id, filename, entities, specs)

        monkeypatch.setattr(worker_module, "project_document_entities", project_or_raise)

        status, processed, failed = tenant.run("run-1", ["doc-bad", "doc-good"])
        assert (status, processed, failed) == ("completed", 1, 1)
        assert tenant.count("document_entities", "doc-bad") == 0
        assert tenant.count("extracted_entities", "doc-bad") == 0
        assert tenant.count("document_entities", "doc-good") > 0
        assert tenant.count("subject") == 1


class TestReconciliationHappensOncePerRun:
    """verification.md rows 79, 80, 84"""

    async def test_reconciliation_runs_exactly_once_for_a_multi_document_run(
        self, tenant, monkeypatch
    ):
        tenant.define("PER", "e_per")
        for i in range(3):
            tenant.add_document(f"doc-{i}", filename=f"{i}.pdf")
        _predict(monkeypatch, _PER_ORG)

        calls = []
        real_reconcile = worker_module.reconcile_entity_tables_sync

        def counting_reconcile(conn, schema, definitions):
            calls.append(schema)
            return real_reconcile(conn, schema, definitions)

        monkeypatch.setattr(worker_module, "reconcile_entity_tables_sync", counting_reconcile)

        status, processed, failed = tenant.run("run-1", ["doc-0", "doc-1", "doc-2"])
        assert (status, processed, failed) == ("completed", 3, 0)
        assert len(calls) == 1

    async def test_a_freshly_provisioned_tenant_extracts_on_its_first_run(
        self, tenant, monkeypatch
    ):
        # `TenantService.create_tenant` clones `tenant_template` via pg_tables + CREATE TABLE
        # (LIKE ...), which carries no generated tables. Run-start reconciliation is the only
        # thing standing between that and a run that fails every document.
        tenant.define("PER", "e_per")
        tenant.add_document("doc-1")
        _predict(monkeypatch, _PER_ORG)

        assert "e_per" not in {
            r[0] for r in tenant.rows("SELECT tablename FROM pg_tables WHERE schemaname = '{s}'")
        }
        status, processed, failed = tenant.run("run-1", ["doc-1"])
        assert (status, processed, failed) == ("completed", 1, 0)
        assert tenant.count("e_per", "doc-1") == 1

    async def test_no_ddl_is_emitted_inside_a_per_document_transaction(
        self, tenant, monkeypatch
    ):
        tenant.define("PER", "e_per")
        tenant.add_document("doc-1")
        _predict(monkeypatch, _PER_ORG)

        seen: list[str] = []
        real_project = worker_module.project_document_entities

        def recording_project(conn, schema, document_id, filename, entities, specs):
            from src.extraction_service.services.relational_projection import (
                build_projection_statements,
            )

            seen.extend(
                sql
                for sql, _params in build_projection_statements(
                    schema, document_id, filename, entities, specs
                )
            )
            return real_project(conn, schema, document_id, filename, entities, specs)

        monkeypatch.setattr(worker_module, "project_document_entities", recording_project)
        tenant.run("run-1", ["doc-1"])

        assert seen
        for sql in seen:
            assert sql.split()[0] in ("INSERT", "DELETE")


class TestTheProjectedListIsTheEavList:
    """verification.md rows 5, 23"""

    async def test_the_projection_receives_the_same_object_the_eav_store_receives(
        self, tenant, monkeypatch
    ):
        tenant.define("PER", "e_per")
        tenant.add_document("doc-1")
        _predict(monkeypatch, _PER_ORG)

        captured: dict = {}
        real_insert = worker_module.insert_document_entities
        real_project = worker_module.project_document_entities

        def capture_insert(conn, schema, document_id, entities):
            captured["eav"] = entities
            return real_insert(conn, schema, document_id, entities)

        def capture_project(conn, schema, document_id, filename, entities, specs):
            captured["projected"] = entities
            return real_project(conn, schema, document_id, filename, entities, specs)

        monkeypatch.setattr(worker_module, "insert_document_entities", capture_insert)
        monkeypatch.setattr(worker_module, "project_document_entities", capture_project)

        tenant.run("run-1", ["doc-1"])

        # Not merely equal — the same list. Anything else would mean the projection re-derived
        # its input, which is the coupling the single-write-point rule exists to prevent.
        assert captured["projected"] is captured["eav"]


class TestReExtractionIsTheMigrationPath:
    """verification.md row 34 — the supported answer to an unprojected tenant.

    A tenant whose documents were extracted before the projection shipped has full EAV data
    and an empty relational surface. There is no backfill: promoting a model version makes
    every document eligible again, `run_batch_extraction` reconciles the schema before the
    document loop, and the surface is repopulated by the ordinary extraction path.
    """

    @staticmethod
    async def _coverage(engine, schema):
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from src.chat_api.services.sql_generator import SQLGenerator
        from src.shared.entity_views import EntityDefinitionSpec, build_query_surface

        surface = build_query_surface([
            EntityDefinitionSpec(name="PER", sql_identifier="e_per"),
        ])
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            reason = await SQLGenerator.__new__(SQLGenerator)._coverage_reason(
                session, schema, surface, None
            )
            await session.rollback()
        return reason

    async def test_re_extraction_repopulates_the_surface_and_restores_answers(
        self, tenant, engine, monkeypatch
    ):
        tenant.define("PER", "e_per")
        tenant.add_document("doc-1")
        _predict(monkeypatch, _PER_ORG)
        tenant.run("run-1", ["doc-1"])
        assert tenant.count("e_per", "doc-1") == 1

        # The state of a tenant extracted before the projection shipped: EAV rows, no
        # relational rows. Produced here by deleting them rather than by simulating an older
        # worker, because the condition the probe reads is exactly this one.
        with tenant.engine.begin() as conn:
            conn.execute(text(f'DELETE FROM "{tenant.schema}".e_per'))
            conn.execute(text(f'DELETE FROM "{tenant.schema}".subject'))
        assert tenant.count("document_entities", "doc-1") > 0

        reason = await self._coverage(engine, tenant.schema)
        assert reason is not None and "holds no rows" in reason

        # The documented remedy: promote a model version and re-run batch extraction. The run
        # reconciles the schema first, so a tenant whose tables are missing entirely recovers
        # by the same path.
        monkeypatch.setattr(worker_module, "_get_active_model_version", lambda tenant_id: "2")
        _predict(monkeypatch, _PER_ORG, model_version="2")
        status, processed, failed = tenant.run("run-2", ["doc-1"])

        assert (status, processed, failed) == ("completed", 1, 0)
        assert tenant.count("subject") == 1
        assert tenant.count("e_per", "doc-1") == 1
        assert await self._coverage(engine, tenant.schema) is None

        # And the question the surface could not answer a moment ago now answers from it.
        assert tenant.rows(
            'SELECT k.value FROM "{s}".e_per k '
            'JOIN "{s}".subject s ON s.document_id = k.document_id'
        ) == [("Arjun",)]


class TestProjectionAfterAValueKindChange:
    """verification.md row 10 — the observed corruption, reproduced and then prevented.

    `PHONE_NUMBER` declared `value_kind = number` over a physically `TEXT` column. The
    projection reads the catalog, so it wrote `entity.value_number` — a float — into a text
    column, and the extracted `'7708888801'` was stored as `'7708888801.0'`. Once the column
    follows the catalog, the representation the catalog names is the representation the column
    can hold.
    """

    _PHONE = [{"token": "7708888801", "label": "B-PHONE_NUMBER", "confidence": 0.95}]

    def _set_value_kind(self, tenant, name, value_kind):
        with tenant.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE public.entity_definitions SET value_kind = :kind "
                    "WHERE tenant_id = :tid AND name = :name"
                ),
                {"kind": value_kind, "tid": tenant.tenant_id, "name": name},
            )

    def _column_type(self, tenant, column):
        return tenant.rows(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = 'subject' AND column_name = :c",
            s=tenant.schema, c=column,
        )[0][0]

    async def test_a_text_definition_projects_the_surface_value(self, tenant, monkeypatch):
        tenant.define("PHONE_NUMBER", "e_phone_number", cardinality="single")
        tenant.add_document("doc-1", text_body="7708888801")
        _predict(monkeypatch, self._PHONE)

        tenant.run("run-1", ["doc-1"])

        assert self._column_type(tenant, "phone_number") == "text"
        assert tenant.rows('SELECT phone_number FROM "{s}".subject') == [("7708888801",)]

    async def test_the_column_follows_the_kind_and_the_projection_follows_the_column(
        self, tenant, monkeypatch
    ):
        """The whole chain in one test: catalog changes, reconcile converges the column, the
        next extraction writes the representation the new kind selects — into a column that can
        hold it."""
        tenant.define("PHONE_NUMBER", "e_phone_number", cardinality="single")
        tenant.add_document("doc-1", text_body="7708888801")
        _predict(monkeypatch, self._PHONE)
        tenant.run("run-1", ["doc-1"])

        self._set_value_kind(tenant, "PHONE_NUMBER", "number")

        # Run-start reconciliation converges the column before any document is projected.
        monkeypatch.setattr(worker_module, "_get_active_model_version", lambda tenant_id: "2")
        _predict(monkeypatch, self._PHONE, model_version="2")
        tenant.run("run-2", ["doc-1"])

        assert self._column_type(tenant, "phone_number") == "double precision"
        assert tenant.rows('SELECT phone_number FROM "{s}".subject') == [(7708888801.0,)]

    async def test_changing_back_to_text_restores_the_surface_value(self, tenant, monkeypatch):
        """The correction the live misconfiguration needed: the value comes back as the
        extracted text, not as a float rendered into a string."""
        tenant.define("PHONE_NUMBER", "e_phone_number", cardinality="single", value_kind="number")
        tenant.add_document("doc-1", text_body="7708888801")
        _predict(monkeypatch, self._PHONE)
        tenant.run("run-1", ["doc-1"])
        assert self._column_type(tenant, "phone_number") == "double precision"

        self._set_value_kind(tenant, "PHONE_NUMBER", "text")
        monkeypatch.setattr(worker_module, "_get_active_model_version", lambda tenant_id: "2")
        _predict(monkeypatch, self._PHONE, model_version="2")
        tenant.run("run-2", ["doc-1"])

        assert self._column_type(tenant, "phone_number") == "text"
        # `'7708888801'`, not `'7708888801.0'` — the surface value, not a float round-trip.
        assert tenant.rows('SELECT phone_number FROM "{s}".subject') == [("7708888801",)]

    async def test_the_entity_store_is_unchanged_by_the_kind_change(self, tenant, monkeypatch):
        """`document_entities` is the system of record: it holds the extracted value through
        every kind change, which is what makes clearing the derived column safe."""
        tenant.define("PHONE_NUMBER", "e_phone_number", cardinality="single")
        tenant.add_document("doc-1", text_body="7708888801")
        _predict(monkeypatch, self._PHONE)
        tenant.run("run-1", ["doc-1"])

        self._set_value_kind(tenant, "PHONE_NUMBER", "number")
        monkeypatch.setattr(worker_module, "_get_active_model_version", lambda tenant_id: "2")
        _predict(monkeypatch, self._PHONE, model_version="2")
        tenant.run("run-2", ["doc-1"])

        assert tenant.rows(
            'SELECT entity_value FROM "{s}".document_entities WHERE entity_type = :t',
            t="PHONE_NUMBER",
        ) == [("7708888801",)]
