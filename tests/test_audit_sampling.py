"""Audit sampling of the auto-accept path.

Covers verification.md rows 21-23.

The accept path is otherwise the only path in this change with no feedback whatsoever, so these
tests are the only ones that say anything about whether a confidently-wrong model would ever be
noticed (design.md Decision 6).

Row 23 is asserted twice over, because "the unsampled are unaffected" is the property an audit
most plausibly breaks: once on the disposition of every unsampled prediction, and once on the
absence of spans, since an audit that quietly produced training data would have changed the
accept path's meaning even while leaving its dispositions alone (design.md Decision 16).
"""

import os
import random

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.annotation_service.main import app
from src.annotation_service.services.audit_sampling import (
    DISPOSITION_AGREE,
    agreement_rate,
    audit_sample_size,
    draw_sample,
)
from src.shared.config import settings
from tests.confidence_review_support import (
    ORG_END,
    ORG_START,
    add_document,
    add_prediction,
    add_run,
    auth_header,
    drop_test_schemas,
    make_tenant,
)


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


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _accepted_population(engine, tenant, count, model_version="3"):
    """`count` auto-accepted predictions from the tenant's serving model.

    The model is promoted as well as named on the predictions, because an audit is scoped to the
    version actually serving: a population spanning versions would give one rate describing
    several models at once.
    """
    doc_id = await add_document(engine, tenant)
    run_id = await add_run(engine, tenant, doc_id, model_version=model_version)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {tenant['schema']}.model_versions "
                "(id, tenant_id, version, status, active_flag) "
                "VALUES (:id, :tid, :v, 'promoted', true) ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": f"mv-{tenant['tid']}-{model_version}",
                "tid": tenant["tid"],
                "v": int(model_version),
            },
        )
    ids = []
    for _ in range(count):
        ids.append(
            await add_prediction(
                engine,
                tenant,
                run_id,
                doc_id,
                confidence=0.97,
                disposition="accepted",
                model_version=model_version,
            )
        )
    return doc_id, run_id, ids


async def _open_audit(tenant):
    async with await _client() as client:
        return await client.post("/api/v1/audits", headers=auth_header(tenant["tid"]))


async def _complete_audit(tenant, audit_id, judgements):
    async with await _client() as client:
        return await client.post(
            f"/api/v1/audits/{audit_id}/complete",
            json={"judgements": judgements},
            headers=auth_header(tenant["tid"]),
        )


async def _dispositions(engine, schema):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT id, disposition FROM {schema}.routed_predictions ORDER BY id"
            )
        )
        return dict(result.fetchall())


class TestSampleSizing:
    """Decision 13's formula, before any database. The floor and the cap are the whole point of
    the rule, and both are boundary behaviour."""

    def test_the_floor_applies_on_a_small_tenant(self):
        # 5% of 100 is 5, which would be too few to say anything; the floor of 20 wins.
        assert audit_sample_size(100, floor=20, fraction=0.05, cap=100) == 20

    def test_the_fraction_applies_in_the_middle(self):
        assert audit_sample_size(1000, floor=20, fraction=0.05, cap=100) == 50

    def test_the_cap_applies_on_a_large_tenant(self):
        assert audit_sample_size(100_000, floor=20, fraction=0.05, cap=100) == 100

    def test_a_population_below_the_floor_is_audited_whole(self):
        assert audit_sample_size(7, floor=20, fraction=0.05, cap=100) == 7

    def test_an_empty_population_draws_nothing(self):
        assert audit_sample_size(0, floor=20, fraction=0.05, cap=100) == 0

    def test_the_shipped_configuration_matches_the_decision(self):
        """Decision 13 as configured: weekly, max(20, 5%), capped at 100."""
        assert settings.audit_interval_days == 7
        assert settings.audit_sample_floor == 20
        assert settings.audit_sample_fraction == 0.05
        assert settings.audit_sample_cap == 100


class TestAuditSampleRandomAndRecorded:
    """Row 21."""

    async def test_audit_sample_random_and_recorded(self, engine):
        """500 auto-accepted predictions, a sample drawn from that population, and the drawn
        identities written down."""
        tenant = await make_tenant(engine)
        _, _, ids = await _accepted_population(engine, tenant, 60)

        resp = await _open_audit(tenant)

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["population_size"] == 60
        # max(20, ceil(0.05 * 60)) = 20.
        assert body["sample_size"] == 20
        assert len(body["predictions"]) == 20

        sampled = {p["id"] for p in body["predictions"]}
        assert sampled <= set(ids)

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    f"SELECT sampled_prediction_ids, sample_size, population_size, model_version "
                    f"FROM {tenant['schema']}.audit_samples"
                )
            )
            rows = result.fetchall()

        assert len(rows) == 1
        recorded_ids, sample_size, population_size, model_version = rows[0]
        assert set(recorded_ids) == sampled, "the drawn identities are what was recorded"
        assert sample_size == 20
        assert population_size == 60
        assert model_version == "3"

    async def test_the_sample_is_not_simply_the_first_n(self, engine):
        """Randomness, demonstrated rather than asserted. The first N of an ordered population
        are frequently the most similar rows in it, and a rate measured over them would not
        generalise — which is why change 4's `draw_sample` is reused here."""
        tenant = await make_tenant(engine)
        _, _, ids = await _accepted_population(engine, tenant, 60)

        resp = await _open_audit(tenant)
        sampled = {p["id"] for p in resp.json()["predictions"]}

        # With 20 drawn uniformly from 60, being exactly the first 20 in insertion order has
        # probability ~1 / C(60,20) — small enough that seeing it means the draw is not random.
        assert sampled != set(ids[:20])

    def test_the_draw_is_change_fours_implementation(self):
        """Task 7.1 asks for change 4's sampling logic to be reused rather than reimplemented.
        Asserted by identity, not by behaviour: two implementations that agree today are still
        two implementations that can diverge."""
        from src.annotation_service.services import batch_acceptance

        assert draw_sample is batch_acceptance.draw_sample
        assert agreement_rate is batch_acceptance.agreement_rate

    async def test_an_empty_population_records_no_audit(self, engine):
        """A recorded audit with a null rate is a measurement that never happened."""
        tenant = await make_tenant(engine)

        resp = await _open_audit(tenant)

        assert resp.status_code == 204
        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT COUNT(*) FROM {tenant['schema']}.audit_samples")
            )
            assert result.scalar() == 0

    async def test_an_already_audited_prediction_is_not_drawn_again(self, engine):
        """The audited rows are still `accepted` and still in the table (Decision 16), so what
        excludes them from the next draw is the audit outcome recorded against them."""
        tenant = await make_tenant(engine)
        await _accepted_population(engine, tenant, 25)

        first = await _open_audit(tenant)
        first_ids = [p["id"] for p in first.json()["predictions"]]
        await _complete_audit(
            tenant,
            first.json()["audit_id"],
            [{"prediction_id": pid, "outcome": "confirmed"} for pid in first_ids],
        )

        second = await _open_audit(tenant)

        assert second.status_code == 201, second.text
        assert second.json()["population_size"] == 5, "25 less the 20 already audited"
        assert not set(p["id"] for p in second.json()["predictions"]) & set(first_ids)


    async def test_predictions_from_a_superseded_version_are_not_audited(self, engine):
        """An audit measures the model in use. What a superseded version got wrong cannot
        change what to do next, and folding it in would give one rate describing two models."""
        tenant = await make_tenant(engine)
        await _accepted_population(engine, tenant, 25, model_version="2")
        await _accepted_population(engine, tenant, 25, model_version="3")

        resp = await _open_audit(tenant)

        assert resp.status_code == 201, resp.text
        assert resp.json()["model_version"] == "3", "the promoted version is the serving one"
        assert resp.json()["population_size"] == 25, "only the version-3 predictions"


class TestAuditAgreementRateRecorded:
    """Row 22."""

    async def test_audit_agreement_rate_recorded(self, engine):
        """The rate, the sample size, and the audited model version — all three, because a rate
        alone is not evidence."""
        tenant = await make_tenant(engine)
        await _accepted_population(engine, tenant, 25)

        opened = (await _open_audit(tenant)).json()
        sampled = [p["id"] for p in opened["predictions"]]
        # 15 agree, 5 disagree: an exactly-known rate of 0.75.
        judgements = [
            {"prediction_id": pid, "outcome": "confirmed"} for pid in sampled[:15]
        ] + [{"prediction_id": pid, "outcome": "rejected"} for pid in sampled[15:]]

        resp = await _complete_audit(tenant, opened["audit_id"], judgements)

        assert resp.status_code == 200, resp.text
        assert resp.json()["agreement_rate"] == pytest.approx(0.75)

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    f"SELECT agreement_rate, reviewed_count, agreed_count, sample_size, "
                    f"       model_version, status FROM {tenant['schema']}.audit_samples"
                )
            )
            row = result.fetchone()

        rate, reviewed, agreed, sample_size, model_version, status = row
        assert rate == pytest.approx(0.75)
        assert (agreed, reviewed) == (15, 20)
        assert sample_size == 20
        assert model_version == "3"
        assert status == "completed"

    async def test_each_judgement_is_recorded_as_an_audit_outcome(self, engine):
        """The audit route uses the same outcome record as queue review, which is what makes
        the two agreement rates comparable at all."""
        tenant = await make_tenant(engine)
        await _accepted_population(engine, tenant, 25)

        opened = (await _open_audit(tenant)).json()
        sampled = [p["id"] for p in opened["predictions"]]
        await _complete_audit(
            tenant,
            opened["audit_id"],
            [{"prediction_id": pid, "outcome": "confirmed"} for pid in sampled],
        )

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    f"SELECT origin, COUNT(*) FROM {tenant['schema']}.review_outcomes "
                    "GROUP BY origin"
                )
            )
            by_origin = dict(result.fetchall())

        assert by_origin == {"audit": 20}

    async def test_a_judgement_outside_the_drawn_sample_is_refused(self, engine):
        """A rate computed over a sample that is not the recorded one is the unfalsifiable
        measurement that storing the drawn identities exists to prevent."""
        tenant = await make_tenant(engine)
        _, _, ids = await _accepted_population(engine, tenant, 25)

        opened = (await _open_audit(tenant)).json()
        sampled = set(p["id"] for p in opened["predictions"])
        outsider = next(pid for pid in ids if pid not in sampled)

        resp = await _complete_audit(
            tenant,
            opened["audit_id"],
            [{"prediction_id": outsider, "outcome": "confirmed"}],
        )

        assert resp.status_code == 422
        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT status FROM {tenant['schema']}.audit_samples")
            )
            assert result.scalar() == "in_review", "the audit was not closed"

    async def test_completing_an_audit_twice_is_refused(self, engine):
        tenant = await make_tenant(engine)
        await _accepted_population(engine, tenant, 25)

        opened = (await _open_audit(tenant)).json()
        judgements = [
            {"prediction_id": p["id"], "outcome": "confirmed"} for p in opened["predictions"]
        ]
        first = await _complete_audit(tenant, opened["audit_id"], judgements)
        second = await _complete_audit(tenant, opened["audit_id"], judgements)

        assert first.status_code == 200
        assert second.status_code == 409


class TestAuditDoesNotAlterUnsampled:
    """Row 23."""

    async def test_audit_does_not_alter_unsampled(self, engine):
        """The spec's scenario in miniature: a population, a sample, some sampled predictions
        found incorrect, and every unsampled prediction still accepted."""
        tenant = await make_tenant(engine)
        _, _, ids = await _accepted_population(engine, tenant, 60)
        before = await _dispositions(engine, tenant["schema"])

        opened = (await _open_audit(tenant)).json()
        sampled = [p["id"] for p in opened["predictions"]]
        unsampled = [pid for pid in ids if pid not in sampled]
        assert len(unsampled) == 40

        # Half the sample judged wrong, which is the case most likely to tempt an
        # implementation into "fixing" the rest.
        judgements = [
            {"prediction_id": pid, "outcome": "rejected"} for pid in sampled[:10]
        ] + [{"prediction_id": pid, "outcome": "confirmed"} for pid in sampled[10:]]
        resp = await _complete_audit(tenant, opened["audit_id"], judgements)
        assert resp.status_code == 200, resp.text

        after = await _dispositions(engine, tenant["schema"])
        for pid in unsampled:
            assert after[pid] == "accepted" == before[pid]

    async def test_an_audit_does_not_consume_the_population_it_measured(self, engine):
        """Decision 16: the sampled predictions keep their accepted disposition too. An
        instrument that consumed what it measured would make successive `population_size`
        figures non-comparable."""
        tenant = await make_tenant(engine)
        _, _, ids = await _accepted_population(engine, tenant, 25)

        opened = (await _open_audit(tenant)).json()
        sampled = [p["id"] for p in opened["predictions"]]
        await _complete_audit(
            tenant,
            opened["audit_id"],
            [{"prediction_id": pid, "outcome": "rejected"} for pid in sampled],
        )

        after = await _dispositions(engine, tenant["schema"])
        assert len(after) == 25, "no prediction was deleted"
        assert set(after.values()) == {"accepted"}

    async def test_an_audit_creates_no_training_data(self, engine):
        """Decision 16: accumulation records new evidence about what the model gets wrong.
        Filling it from high-confidence predictions a reviewer agreed with would bias the
        training set toward what the model already handles, and would make the figure grow with
        audit frequency."""
        tenant = await make_tenant(engine)
        await _accepted_population(engine, tenant, 25)

        opened = (await _open_audit(tenant)).json()
        await _complete_audit(
            tenant,
            opened["audit_id"],
            [
                {"prediction_id": p["id"], "outcome": "confirmed"}
                for p in opened["predictions"]
            ],
        )

        async with engine.connect() as conn:
            spans = await conn.execute(
                text(f"SELECT COUNT(*) FROM {tenant['schema']}.spans")
            )
            assert spans.scalar() == 0
            provenance = await conn.execute(
                text(f"SELECT COUNT(*) FROM {tenant['schema']}.span_review_provenance")
            )
            assert provenance.scalar() == 0

        async with await _client() as client:
            report = await client.get(
                "/api/v1/review-accumulation", headers=auth_header(tenant["tid"])
            )
        assert report.json()["spans_accumulated"] == 0, (
            "auditing must not grow the accumulation figure"
        )

    async def test_an_audit_starts_no_training_job(self, engine, monkeypatch):
        """The same absence row 20 checks, at the other surface that could plausibly trip it."""
        from src.annotation_service.celery_app import celery_app

        dispatched = []
        for method in ("send_task", "apply_async"):
            if hasattr(celery_app, method):
                monkeypatch.setattr(
                    celery_app,
                    method,
                    lambda *a, _m=method, **k: dispatched.append((_m, a, k)),
                )

        tenant = await make_tenant(engine)
        await _accepted_population(engine, tenant, 25)
        opened = (await _open_audit(tenant)).json()
        await _complete_audit(
            tenant,
            opened["audit_id"],
            [
                {"prediction_id": p["id"], "outcome": "rejected"}
                for p in opened["predictions"]
            ],
        )

        assert dispatched == [], f"something was dispatched: {dispatched}"
