"""Verification for per-tenant integration profiles — verification.md rows 43-63.

The rows that matter most here are the negative ones: a profile that can be activated
without validation, or that accepts a credential value in a secret field, is a profile
whose guarantees are decorative.
"""

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

os.environ.setdefault(
    "NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test"
)
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.document_service.ingestion import DocumentIngestionService, RecordingDispatcher
from src.shared.document_retention import RETENTION_PLATFORM_BLOB
from src.shared.integration_profile import (
    STATUS_ACTIVE,
    STATUS_DRAFT,
    STATUS_ERROR,
    STATUS_PAUSED,
    STATUS_RETIRED,
    STATUS_VALIDATED,
    InvalidSecretReference,
    ProfileValidationError,
    SecretResolutionError,
    TransitionRejected,
    UnknownConfigurationKey,
    activate_profile,
    load_profile,
    resolve_for_tenant,
    transition_profile,
    validate_profile,
    write_profile,
)
from src.shared.integration_profile.store import PROFILE_TABLE

from tests.test_ingestion_boundary import (
    FakeStore,
    normalized,
    session_factory,  # noqa: F401
    tenant,  # noqa: F401
)


async def ensure_profile(session_factory, tenant_id, status=STATUS_DRAFT):
    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {PROFILE_TABLE} (tenant_id, status) VALUES (:tid, :st) "
                f"ON CONFLICT (tenant_id) DO UPDATE SET status = :st"
            ),
            {"tid": tenant_id, "st": status},
        )
        await session.commit()


async def read_row(session_factory, tenant_id):
    async with session_factory() as session:
        return (
            await session.execute(
                text(f"SELECT * FROM {PROFILE_TABLE} WHERE tenant_id = :tid"),
                {"tid": tenant_id},
            )
        ).fetchone()


# --- Rows 43-45: existence, placement, and readability ---------------------------------


@pytest.mark.asyncio
async def test_row_43_every_tenant_has_a_profile_selecting_the_platform_defaults(
    tenant, session_factory
):
    await ensure_profile(session_factory, tenant["tenant_id"])
    async with session_factory() as session:
        profile = await load_profile(session, tenant["tenant_id"])

    assert profile.selections() == {
        "source_adapter": "platform_upload",
        "content_store_adapter": "platform_minio",
        "relational_adapter": "platform_postgresql",
        "index_adapter": "platform_pgvector",
    }
    assert profile.retention_mode == RETENTION_PLATFORM_BLOB


@pytest.mark.asyncio
async def test_row_44_the_profile_table_lives_in_public(session_factory):
    assert PROFILE_TABLE.startswith("public."), PROFILE_TABLE

    async with session_factory() as session:
        schemas = (
            await session.execute(
                text(
                    "SELECT table_schema FROM information_schema.tables "
                    "WHERE table_name = 'tenant_integration_profiles'"
                )
            )
        ).fetchall()
    found = {r[0] for r in schemas}
    assert found == {"public"}, found
    assert not any(s.startswith("tenant_") for s in found)


@pytest.mark.asyncio
async def test_row_45_a_profile_is_readable_when_the_tenant_schema_is_unavailable(
    tenant, session_factory
):
    """The reason the profile is control-plane state: the platform must be able to read a
    tenant's configuration precisely when that tenant's own infrastructure is down."""
    await ensure_profile(session_factory, tenant["tenant_id"])

    async with session_factory() as session:
        await session.execute(text(f"DROP SCHEMA {tenant['schema']} CASCADE"))
        await session.commit()

    async with session_factory() as session:
        profile = await load_profile(session, tenant["tenant_id"])
    assert profile.tenant_id == tenant["tenant_id"]


# --- Rows 46-48: recordable but not executable -----------------------------------------


@pytest.mark.asyncio
async def test_row_46_a_non_default_selection_may_be_recorded(tenant, session_factory):
    await ensure_profile(session_factory, tenant["tenant_id"])
    async with session_factory() as session:
        await write_profile(
            session, tenant["tenant_id"], selections={"index_adapter": "external_index"}
        )

    row = await read_row(session_factory, tenant["tenant_id"])
    assert row.index_adapter == "external_index"
    assert row.status == STATUS_DRAFT


@pytest.mark.asyncio
async def test_row_47_a_non_default_selection_cannot_be_activated(
    tenant, session_factory
):
    await ensure_profile(session_factory, tenant["tenant_id"])
    async with session_factory() as session:
        await write_profile(
            session,
            tenant["tenant_id"],
            selections={"relational_adapter": "tenant_postgresql"},
        )
        await validate_profile(session, tenant["tenant_id"])

        with pytest.raises(TransitionRejected) as excinfo:
            await activate_profile(session, tenant["tenant_id"])

    assert "tenant_postgresql" in str(excinfo.value)
    assert "not yet supported" in str(excinfo.value)
    row = await read_row(session_factory, tenant["tenant_id"])
    assert row.status != STATUS_ACTIVE


@pytest.mark.asyncio
async def test_row_48_ingestion_uses_executable_adapters_regardless_of_the_record(
    tenant, session_factory
):
    await ensure_profile(session_factory, tenant["tenant_id"])
    async with session_factory() as session:
        await write_profile(
            session, tenant["tenant_id"], selections={"source_adapter": "keka"}
        )

    durable = FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable
    )
    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    # The platform content store served it, and the recorded selection had no effect.
    assert durable.puts == [result.storage_reference]
    assert result.content_store_kind == "platform_minio"


# --- Rows 49-52: typed, allowlisted configuration --------------------------------------


@pytest.mark.asyncio
async def test_row_49_an_unknown_configuration_key_is_rejected(tenant, session_factory):
    await ensure_profile(session_factory, tenant["tenant_id"])
    async with session_factory() as session:
        with pytest.raises(UnknownConfigurationKey) as excinfo:
            await write_profile(
                session,
                tenant["tenant_id"],
                configuration={"keka": {"base_url": "https://x", "sneaky_password": "p"}},
            )
    assert "sneaky_password" in str(excinfo.value)

    row = await read_row(session_factory, tenant["tenant_id"])
    assert row.configuration == {}


@pytest.mark.asyncio
async def test_row_50_a_secret_field_must_hold_a_reference_not_a_value(
    tenant, session_factory
):
    await ensure_profile(session_factory, tenant["tenant_id"])
    async with session_factory() as session:
        with pytest.raises(InvalidSecretReference) as excinfo:
            await write_profile(
                session,
                tenant["tenant_id"],
                secret_references={"keka": {"api_token_ref": "sk-live-abcdef123456"}},
            )

    # The rejection names the field and never echoes the value it refused.
    assert "api_token_ref" in str(excinfo.value)
    assert "sk-live-abcdef123456" not in str(excinfo.value)

    row = await read_row(session_factory, tenant["tenant_id"])
    assert row.secret_references == {}


@pytest.mark.asyncio
async def test_row_51_a_valid_reference_is_stored_verbatim(tenant, session_factory):
    await ensure_profile(session_factory, tenant["tenant_id"])
    reference = "vault://tenants/acme/keka/api-token"
    async with session_factory() as session:
        await write_profile(
            session,
            tenant["tenant_id"],
            secret_references={"keka": {"api_token_ref": reference}},
        )

    row = await read_row(session_factory, tenant["tenant_id"])
    assert row.secret_references == {"keka": {"api_token_ref": reference}}


@pytest.mark.asyncio
async def test_row_52_validation_does_not_depend_on_value_inspection(
    tenant, session_factory
):
    """A non-secret string field is accepted on its declared type, even when the value
    happens to look like a credential. Heuristics reject innocent strings and miss real
    secrets; the schema is what is enforced."""
    await ensure_profile(session_factory, tenant["tenant_id"])
    credential_shaped = "AKIAIOSFODNN7EXAMPLE"
    async with session_factory() as session:
        await write_profile(
            session,
            tenant["tenant_id"],
            configuration={"s3": {"bucket": credential_shaped, "region": "us-east-1"}},
        )

    row = await read_row(session_factory, tenant["tenant_id"])
    assert row.configuration["s3"]["bucket"] == credential_shaped


@pytest.mark.asyncio
async def test_a_wrongly_typed_configuration_value_is_rejected(tenant, session_factory):
    await ensure_profile(session_factory, tenant["tenant_id"])
    async with session_factory() as session:
        with pytest.raises(ProfileValidationError):
            await write_profile(
                session, tenant["tenant_id"], configuration={"keka": {"page_size": "many"}}
            )


# --- Rows 53-57: the status model -------------------------------------------------------


@pytest.mark.asyncio
async def test_row_53_a_draft_profile_does_not_serve_requests(tenant, session_factory):
    await ensure_profile(session_factory, tenant["tenant_id"], STATUS_DRAFT)
    async with session_factory() as session:
        await write_profile(
            session, tenant["tenant_id"], selections={"index_adapter": "external_index"}
        )

    durable = FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable
    )
    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    assert result.content_store_kind == "platform_minio"
    assert durable.puts


@pytest.mark.asyncio
async def test_row_54_activation_from_draft_is_refused(tenant, session_factory):
    await ensure_profile(session_factory, tenant["tenant_id"], STATUS_DRAFT)
    async with session_factory() as session:
        with pytest.raises(TransitionRejected):
            await activate_profile(session, tenant["tenant_id"])

    row = await read_row(session_factory, tenant["tenant_id"])
    assert row.status == STATUS_DRAFT


@pytest.mark.asyncio
async def test_row_55_an_unresolvable_reference_moves_the_profile_to_error(
    tenant, session_factory, monkeypatch
):
    await ensure_profile(session_factory, tenant["tenant_id"], STATUS_DRAFT)
    monkeypatch.delenv("NER_ABSENT_TENANT_SECRET", raising=False)
    reference = "env://NER_ABSENT_TENANT_SECRET"

    async with session_factory() as session:
        await write_profile(
            session,
            tenant["tenant_id"],
            secret_references={"keka": {"api_token_ref": reference}},
        )

    async with session_factory() as session:
        with pytest.raises(SecretResolutionError):
            await validate_profile(session, tenant["tenant_id"])

    row = await read_row(session_factory, tenant["tenant_id"])
    assert row.status == STATUS_ERROR
    assert reference in row.status_reason
    assert "not_found" in row.status_reason
    # The reason names the reference and its failure class, and nothing else.
    assert "NER_ABSENT_TENANT_SECRET=" not in row.status_reason


@pytest.mark.asyncio
async def test_row_56_an_errored_profile_recovers_only_through_revalidation(
    tenant, session_factory, monkeypatch
):
    await ensure_profile(session_factory, tenant["tenant_id"], STATUS_ERROR)
    async with session_factory() as session:
        with pytest.raises(TransitionRejected):
            await activate_profile(session, tenant["tenant_id"])

        await validate_profile(session, tenant["tenant_id"])

    row = await read_row(session_factory, tenant["tenant_id"])
    assert row.status == STATUS_VALIDATED

    async with session_factory() as session:
        await activate_profile(session, tenant["tenant_id"])
    assert (await read_row(session_factory, tenant["tenant_id"])).status == STATUS_ACTIVE


@pytest.mark.asyncio
async def test_row_57_a_retired_profile_is_terminal(tenant, session_factory):
    await ensure_profile(session_factory, tenant["tenant_id"], STATUS_ACTIVE)
    async with session_factory() as session:
        await transition_profile(session, tenant["tenant_id"], STATUS_RETIRED)

    for requested in (STATUS_DRAFT, STATUS_VALIDATED, STATUS_ACTIVE, STATUS_PAUSED, STATUS_ERROR):
        async with session_factory() as session:
            with pytest.raises(TransitionRejected):
                await transition_profile(session, tenant["tenant_id"], requested)

    assert (await read_row(session_factory, tenant["tenant_id"])).status == STATUS_RETIRED


@pytest.mark.asyncio
async def test_pause_and_resume_are_permitted(tenant, session_factory):
    await ensure_profile(session_factory, tenant["tenant_id"], STATUS_ACTIVE)
    async with session_factory() as session:
        await transition_profile(session, tenant["tenant_id"], STATUS_PAUSED)
    assert (await read_row(session_factory, tenant["tenant_id"])).status == STATUS_PAUSED
    async with session_factory() as session:
        await transition_profile(session, tenant["tenant_id"], STATUS_ACTIVE)
    assert (await read_row(session_factory, tenant["tenant_id"])).status == STATUS_ACTIVE


@pytest.mark.asyncio
async def test_the_status_column_rejects_a_value_outside_the_model(
    tenant, session_factory
):
    await ensure_profile(session_factory, tenant["tenant_id"])
    with pytest.raises(IntegrityError):
        async with session_factory() as session:
            await session.execute(
                text(f"UPDATE {PROFILE_TABLE} SET status = 'whatever' WHERE tenant_id = :t"),
                {"t": tenant["tenant_id"]},
            )
            await session.commit()


# --- Rows 58-61: secrets are references, scoped, and never returned --------------------


@pytest.mark.asyncio
async def test_row_58_administrative_reads_return_references_not_values(
    tenant, session_factory, monkeypatch
):
    monkeypatch.setenv("NER_TEST_TENANT_SECRET", "the-actual-credential")
    reference = "env://NER_TEST_TENANT_SECRET"
    await ensure_profile(session_factory, tenant["tenant_id"])
    async with session_factory() as session:
        await write_profile(
            session,
            tenant["tenant_id"],
            secret_references={"keka": {"api_token_ref": reference}},
        )
        profile = await load_profile(session, tenant["tenant_id"])

    rendered = repr(profile)
    assert reference in rendered
    assert "the-actual-credential" not in rendered

    row = await read_row(session_factory, tenant["tenant_id"])
    for value in row:
        assert "the-actual-credential" not in str(value)


@pytest.mark.asyncio
async def test_row_59_resolution_is_scoped_to_the_owning_tenant(
    tenant, session_factory, monkeypatch
):
    """Holding a reference is not enough: it must be recorded on that tenant's own profile."""
    monkeypatch.setenv("NER_TEST_TENANT_SECRET", "tenant-a-credential")
    reference = "env://NER_TEST_TENANT_SECRET"
    tenant_a = tenant["tenant_id"]
    tenant_b = uuid.uuid4().hex

    await ensure_profile(session_factory, tenant_a)
    async with session_factory() as session:
        await write_profile(
            session, tenant_a, secret_references={"keka": {"api_token_ref": reference}}
        )
        profile_a = await load_profile(session, tenant_a)
        # Tenant B has no profile row, so it gets the defaults: no references at all.
        profile_b = await load_profile(session, tenant_b)

    assert resolve_for_tenant(profile_a, "keka").values["api_token_ref"] == "tenant-a-credential"
    with pytest.raises(SecretResolutionError) as excinfo:
        resolve_for_tenant(profile_b, "keka")
    assert excinfo.value.failure_class == "not_recorded_for_tenant"


@pytest.mark.asyncio
async def test_row_60_resolved_credentials_are_never_persisted_or_logged(
    tenant, session_factory, monkeypatch, caplog
):
    secret = "resolved-credential-must-not-appear"
    monkeypatch.setenv("NER_TEST_TENANT_SECRET", secret)
    await ensure_profile(session_factory, tenant["tenant_id"])
    async with session_factory() as session:
        await write_profile(
            session,
            tenant["tenant_id"],
            secret_references={"keka": {"api_token_ref": "env://NER_TEST_TENANT_SECRET"}},
        )
        profile = await load_profile(session, tenant["tenant_id"])

    with caplog.at_level("DEBUG"):
        context = resolve_for_tenant(profile, "keka")

    assert context.values["api_token_ref"] == secret
    assert secret not in caplog.text

    async with session_factory() as session:
        rows = (
            await session.execute(text(f"SELECT * FROM {PROFILE_TABLE}"))
        ).fetchall()
    for row in rows:
        for value in row:
            assert secret not in str(value)


def test_row_61_adapters_receive_values_never_a_reference_or_a_resolver():
    import inspect

    from src.shared.integration_profile.secrets import TenantSecretContext

    # The context an adapter is handed carries resolved values and a tenant, and nothing
    # that could reach a secret source.
    fields = set(TenantSecretContext.__dataclass_fields__)
    assert fields == {"tenant_id", "values"}
    assert not hasattr(TenantSecretContext, "resolve")

    from src.document_service.content_store import minio_store

    source = inspect.getsource(minio_store)
    for forbidden in ("resolve_for_tenant", "secret_references", "_resolve_one", "Resolver"):
        assert forbidden not in source, f"the content-store adapter reaches {forbidden}"


# --- Row 62: profiles are developer-managed ---------------------------------------------


def test_row_62_no_tenant_facing_route_exposes_profile_modification():
    import pathlib

    src_root = pathlib.Path(__file__).resolve().parents[1] / "src"
    offenders = []
    for path in src_root.rglob("*.py"):
        if "integration_profile" in str(path):
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "tenant_integration_profiles" in source or "activate_profile" in source:
            offenders.append(str(path.relative_to(src_root)))
    assert offenders == [], f"profile mutation is reachable from {offenders}"


# --- Row 63: adapter selection is observable -------------------------------------------


@pytest.mark.asyncio
async def test_row_63_ingestion_records_the_adapters_that_served_it(
    tenant, session_factory, caplog
):
    from src.shared.observability.domain_metrics import DOCUMENT_INGESTIONS

    await ensure_profile(session_factory, tenant["tenant_id"])
    async with session_factory() as session:
        await write_profile(
            session,
            tenant["tenant_id"],
            configuration={"s3": {"bucket": "a-tenants-private-bucket-name"}},
        )

    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=FakeStore()
    )
    with caplog.at_level("INFO"):
        async with session_factory() as session:
            await service.ingest(session, normalized(tenant["tenant_id"]))

    record = next(r for r in caplog.records if r.getMessage() == "document_ingested")
    assert record.source_type == "platform_upload"
    assert record.content_store_kind == "platform_minio"
    assert record.retention_mode == "platform_blob"

    # Every recorded value comes from the declared set.
    labels = {label.name: label.values for label in DOCUMENT_INGESTIONS.labels}
    assert record.source_type in labels["source_type"]
    assert record.content_store_kind in labels["content_store_kind"]
    assert record.retention_mode in labels["retention_mode"]

    # And the tenant's own configuration reaches nothing.
    assert "a-tenants-private-bucket-name" not in caplog.text
    for values in labels.values():
        assert "a-tenants-private-bucket-name" not in values
