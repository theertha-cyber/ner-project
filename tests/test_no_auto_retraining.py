"""The prohibition, made checkable.

Covers verification.md rows 14-17.

This file exists because the decision it guards was already made once and then reversed. An
earlier version of this plan had retraining fire automatically once accumulation crossed a
threshold; that was deliberately replaced with a human decision, which makes it the single most
likely thing to be put back by someone who sees a figure of 5000 and concludes the system should
act on it — including as a config-gated feature defaulting to off, which is still a trigger
(verification.md Risk 1).

Every assertion here is about an absence, and absences are not visible in a response body. So
each is checked twice where it can be:

* **Behaviourally**, with `celery_app.send_task` spied on across the real endpoints while the
  figure grows and a run completes. Not stubs — the annotation and training apps, the real
  accumulation query, the real consumed-span writer.
* **Structurally**, by parsing this change's own modules for a training enqueue, a scheduler
  registration, a timer, or a comparison of a figure against a constant. A trigger added behind
  a config flag would pass every behavioural test in this file with the flag off; the source
  scan is what sees it anyway.
"""

import ast
import os
import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.annotation_service.main import app as annotation_app
from src.shared.config import settings
from src.training_service.main import app as training_app
from tests.retraining_support import (
    add_document,
    add_model_version,
    add_run,
    auth_header,
    complete_run,
    dataset_span_ids_now,
    drop_test_schemas,
    make_tenant,
    review_spans,
)

pytestmark = pytest.mark.verification

# Every module this change adds or touches. The structural scans below read all of them, so a
# trigger cannot be hidden in whichever file the scan happened not to name.
CHANGE_MODULES = [
    "src/training_service/services/consumed_spans.py",
    "src/training_service/api/v1/retrain_request.py",
    "src/training_service/api/v1/promotion_evidence.py",
    "src/annotation_service/api/v1/retraining_decision.py",
    "src/annotation_service/services/accumulation.py",
]


@pytest.fixture
async def engine():
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def cleanup(engine):
    yield
    await drop_test_schemas(engine)


class _SendTaskSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, name, args=None, **kwargs):
        self.calls.append((name, args))

        class _Result:
            id = "spied-task-id"

        return _Result()


@pytest.fixture
def send_task_spy(monkeypatch):
    """Spies on every `send_task` this change could reach, not just the training one.

    Both services' Celery apps, so a trigger that reached for the extraction or review queue
    instead of `training.jobs` is caught too. ADR-006 puts training on its own queue; a job
    smuggled onto another one would still be a job.
    """
    from src.annotation_service.api.v1 import llm_prelabel
    from src.training_service.api.v1 import training_jobs

    spy = _SendTaskSpy()
    monkeypatch.setattr(training_jobs.celery_app, "send_task", spy)
    if hasattr(llm_prelabel, "celery_app"):
        monkeypatch.setattr(llm_prelabel.celery_app, "send_task", spy, raising=False)
    return spy


def _annotation_client():
    return AsyncClient(transport=ASGITransport(app=annotation_app), base_url="http://test")


def _training_client():
    return AsyncClient(transport=ASGITransport(app=training_app), base_url="http://test")


async def _job_count(engine, tenant) -> int:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(f"SELECT COUNT(*) FROM {tenant['schema']}.training_jobs")
        )
        return int(result.scalar() or 0)


def _executable_source(path: str) -> str:
    """A module's code with docstrings and comments removed.

    Both are stripped because both discuss triggers at length in these files — a scan that
    matched them would fail on prose explaining why the trigger is absent.
    """
    source = Path(path).read_text(encoding="utf-8")
    code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    return re.sub(r"#.*", "", code)


class TestLargeAccumulationCreatesNoJob:
    """Row 14."""

    async def test_large_accumulation_creates_no_job(self, engine, send_task_spy):
        """The figure grows and nothing happens.

        The spec says 5000; this reads the figure repeatedly as it grows through the real
        endpoint, which is the behaviour under test — a threshold check would live on the read
        path, and 5000 identical resolutions would only make the test slow, not the assertion
        stronger.
        """
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="3")
        await add_model_version(engine, tenant, 3, status="promoted")

        for _ in range(4):
            await review_spans(_annotation_client, engine, tenant, doc_id, run_id, 3)
            async with _annotation_client() as client:
                for path in ("/api/v1/review-accumulation", "/api/v1/retraining-decision"):
                    resp = await client.get(path, headers=auth_header(tenant["tid"]))
                    assert resp.status_code == 200, resp.text

        assert send_task_spy.calls == []
        assert await _job_count(engine, tenant) == 0

    def test_no_module_enqueues_training(self):
        """Structural half: no `send_task`, `delay`, or `apply_async` anywhere in this change.

        Parsed rather than grepped for the call itself, so an enqueue reached through an alias
        still shows up as a call to a name this list contains.
        """
        forbidden = {"send_task", "delay", "apply_async", "send_task_async"}
        for path in CHANGE_MODULES:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    assert node.func.attr not in forbidden, f"{path}: {node.func.attr}"
                if isinstance(node, ast.Attribute):
                    assert node.attr not in forbidden, f"{path}: {node.attr}"

    def test_no_module_registers_a_schedule(self):
        """No cron entry, no beat schedule, no timer.

        design.md Decision 3 names schedules alongside thresholds because a nightly retrain is
        the same decision made by a clock instead of a person.
        """
        forbidden = (
            "beat_schedule",
            "crontab",
            "periodic_task",
            "on_after_configure",
            "add_periodic_task",
            "APScheduler",
            "BackgroundScheduler",
            "threading.Timer",
            "asyncio.create_task",
            "schedule.every",
        )
        for path in CHANGE_MODULES:
            code = _executable_source(path)
            for token in forbidden:
                assert token not in code, f"{path}: {token}"

    def test_no_module_compares_a_figure_to_a_constant(self):
        """No threshold, and no numeric literal that could become one.

        The one comparison constant this change does define — `MATERIAL_DATASET_DIFFERENCE` on
        the promotion surface — gates a sentence about comparability and is checked separately
        in `test_promotion_evidence.py` to have no action behind it. Nothing on the accumulation
        path may define one at all.
        """
        accumulation_path_modules = [
            "src/annotation_service/api/v1/retraining_decision.py",
            "src/annotation_service/services/accumulation.py",
            "src/training_service/services/consumed_spans.py",
        ]
        for path in accumulation_path_modules:
            code = _executable_source(path)
            # No float literal to be a threshold, and no integer above a single digit.
            assert not re.search(r"\b\d+\.\d+\b", code), path
            assert not re.search(r"\b\d{2,}\b", code), path


class TestCompletionDoesNotChainRun:
    """Row 15."""

    async def test_completion_does_not_chain_run(self, engine, send_task_spy):
        """Recording what a run consumed starts nothing.

        Completion's whole effect on the world beyond its own result is the consumed-span
        record. This drives that record through the production writer and then asserts the job
        count is unchanged and nothing was enqueued.
        """
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="3")
        await add_model_version(engine, tenant, 3, status="promoted")
        await review_spans(_annotation_client, engine, tenant, doc_id, run_id, 5)

        jobs_before = await _job_count(engine, tenant)
        dataset = await dataset_span_ids_now(engine, tenant)
        await add_model_version(engine, tenant, 4, status="completed")
        await complete_run(engine, tenant, dataset, version_number=4)

        assert await _job_count(engine, tenant) == jobs_before
        assert send_task_spy.calls == []

    def test_worker_completion_block_creates_no_job(self):
        """Structural: the worker's success branch records and stops.

        Reads the one block this change added to `fine_tune_model` and confirms it contains no
        job creation and no enqueue. The behavioural half above exercises the recording function
        rather than the Celery task — running the task needs a GPU and a model download — so
        this is what covers the call site itself.
        """
        source = Path("src/training_service/worker.py").read_text(encoding="utf-8")
        assert "record_consumed_spans(" in source

        code = re.sub(r"#.*", "", source)
        # The worker enqueues nothing at all: it is what a queue delivers to, not what fills it.
        assert "send_task" not in code
        assert "apply_async" not in code
        assert ".delay(" not in code
        # And it registers no schedule that could fire another run.
        for token in ("beat_schedule", "crontab", "add_periodic_task"):
            assert token not in code, token


class TestCompletionDoesNotSelfPromote:
    """Row 16."""

    async def test_completion_does_not_self_promote(self, engine):
        """Version 4 completes, stays `completed`, and version 3 keeps serving."""
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="3")
        await add_model_version(engine, tenant, 3, status="promoted")
        await review_spans(_annotation_client, engine, tenant, doc_id, run_id, 3)

        dataset = await dataset_span_ids_now(engine, tenant)
        await add_model_version(engine, tenant, 4, status="completed")
        await complete_run(engine, tenant, dataset, version_number=4)

        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    f"SELECT version_number, status FROM {tenant['schema']}.model_versions "
                    "ORDER BY version_number"
                )
            )
            statuses = {int(r[0]): r[1] for r in result.fetchall()}

        assert statuses[4] == "completed"
        assert statuses[3] == "promoted"

        # And the serving version the surfaces report is still 3.
        async with _annotation_client() as client:
            decision = await client.get(
                "/api/v1/retraining-decision", headers=auth_header(tenant["tid"])
            )
        assert decision.json()["serving_model_version"] == "3"

    def test_no_module_promotes(self):
        """Structural: no promote call is reachable from anything this change added.

        `promotion_evidence.py` is included in the scan deliberately — it is the module closest
        to the temptation, since it already knows which version is a candidate and which is
        serving (verification.md Risk 3).
        """
        for path in CHANGE_MODULES + ["src/training_service/worker.py"]:
            code = _executable_source(path)
            for token in ("promote_model", "mlflow_promote", "promote_model_version"):
                assert token not in code, f"{path}: {token}"
            assert "status = 'promoted'" not in code.replace(
                "WHERE status = 'promoted'", ""
            ), path


class TestPromotionRequiresHumanAction:
    """Row 17."""

    async def test_promotion_requires_human_action(self, engine):
        """A completed version nobody promotes never becomes the serving version.

        "Indefinitely" cannot be tested; what can be is that nothing in the system moves it. So
        the surfaces are read repeatedly, the completion path is run, and the status is asserted
        unchanged throughout — every event this change can produce, with the version still
        sitting in `completed` afterwards.
        """
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="3")
        await add_model_version(engine, tenant, 3, status="promoted")
        await add_model_version(engine, tenant, 4, status="completed")
        await review_spans(_annotation_client, engine, tenant, doc_id, run_id, 4)

        async def _version_4_status():
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        f"SELECT status FROM {tenant['schema']}.model_versions "
                        "WHERE version_number = 4"
                    )
                )
                return result.scalar()

        assert await _version_4_status() == "completed"

        dataset = await dataset_span_ids_now(engine, tenant)
        await complete_run(engine, tenant, dataset, version_number=4)
        assert await _version_4_status() == "completed"

        async with _annotation_client() as client:
            for path in ("/api/v1/review-accumulation", "/api/v1/retraining-decision"):
                await client.get(path, headers=auth_header(tenant["tid"]))
        async with _training_client() as client:
            resp = await client.get(
                "/api/v1/training-promotion-evidence/4", headers=auth_header(tenant["tid"])
            )
            assert resp.status_code == 200, resp.text

        # Reading the evidence for promoting version 4 does not promote version 4.
        assert await _version_4_status() == "completed"
        assert resp.json()["candidate"]["status"] == "completed"
