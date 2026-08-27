"""Integration tests for the entity table reconciler against a real tenant schema.

The pure-function half of this layer is covered in `test_entity_views_generator.py`. What is
left here is everything the generated DDL can only be wrong about once a server executes it:
whether `subject` survives a change to its column list without losing rows, whether a
deactivated definition's table and rows genuinely survive, and whether the reconciler tolerates
every schema state that exists in the wild.

Covers verification.md rows 53, 59-63, 65, 68.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.shared.entity_views import (
    SUBJECT_TABLE_NAME,
    EntityDefinitionSpec,
    generated_table_names,
    reconcile_entity_tables,
    reconcile_entity_tables_sync,
    subject_columns,
)

_DOCUMENT_ENTITIES_DDL = """
    CREATE TABLE "{schema}".document_entities (
        id VARCHAR PRIMARY KEY,
        document_id VARCHAR NOT NULL,
        entity_type TEXT NOT NULL,
        entity_value TEXT NOT NULL,
        normalized_value TEXT NOT NULL,
        confidence DOUBLE PRECISION NOT NULL,
        page_number INTEGER,
        char_start INTEGER,
        char_end INTEGER,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        value_kind TEXT,
        value_number DOUBLE PRECISION,
        value_number_high DOUBLE PRECISION,
        value_unit TEXT,
        value_date DATE,
        value_date_high DATE,
        occurrence_count INTEGER NOT NULL DEFAULT 1
    )
"""

_DOCUMENTS_DDL = """
    CREATE TABLE "{schema}".documents (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        filename VARCHAR(255) NOT NULL,
        status VARCHAR(20) DEFAULT 'uploaded',
        created_at TIMESTAMPTZ DEFAULT now()
    )
"""


def _spec(name, identifier, **kwargs):
    return EntityDefinitionSpec(name=name, sql_identifier=identifier, **kwargs)


async def _make_schema(engine, schema, *, with_document_entities=True):
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.execute(text(_DOCUMENTS_DDL.format(schema=schema)))
        if with_document_entities:
            await conn.execute(text(_DOCUMENT_ENTITIES_DDL.format(schema=schema)))


async def _drop_schema(engine, schema):
    async with engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


async def _reconcile(engine, schema, definitions):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        statements = await reconcile_entity_tables(session, schema, definitions)
        await session.commit()
    return statements


async def _tables(engine, schema):
    async with engine.begin() as conn:
        rows = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = :s"), {"s": schema}
        )
    return {r[0] for r in rows.fetchall()}


async def _columns(engine, schema, table):
    async with engine.begin() as conn:
        rows = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t ORDER BY ordinal_position"
            ),
            {"s": schema, "t": table},
        )
    return [r[0] for r in rows.fetchall()]


async def _row_count(engine, schema, table):
    async with engine.begin() as conn:
        result = await conn.execute(text(f'SELECT count(*) FROM "{schema}".{table}'))
    return result.scalar()


async def _insert_child_row(engine, schema, table, doc_id, value):
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f'INSERT INTO "{schema}".{table} '
                "(document_id, value, normalized_value, confidence) "
                "VALUES (:doc, :value, :value, 0.9)"
            ),
            {"doc": doc_id, "value": value},
        )


@pytest_asyncio.fixture
async def schema(engine, setup_database):
    name = f"tenant_tables_{uuid.uuid4().hex[:8]}"
    await _make_schema(engine, name)
    yield name
    await _drop_schema(engine, name)


@pytest.fixture
def sync_engine():
    """The extraction worker's connection idiom, so the sync executor is exercised as it runs."""
    from sqlalchemy import create_engine

    from src.shared.config import settings

    engine = create_engine(settings.database_url_sync)
    yield engine
    engine.dispose()


@pytest.mark.asyncio
class TestReconcilerRepairs:
    """verification.md rows 59-63"""

    async def test_missing_table_created(self, engine, schema):
        await _reconcile(engine, schema, [_spec("SKILL", "e_skill")])
        assert {"e_skill", "subject"} <= await _tables(engine, schema)

        # Created, and actually writable — the projection's inserts run against exactly this
        # shape, and a table that parses but rejects the insert fails at extraction time.
        await _insert_child_row(engine, schema, "e_skill", str(uuid.uuid4()), "python")

    async def test_stale_subject_repaired(self, engine, schema):
        await _reconcile(engine, schema, [_spec("EMAIL", "e_email", cardinality="single")])
        assert "email" in await _columns(engine, schema, "subject")

        await _reconcile(
            engine,
            schema,
            [
                _spec("EMAIL", "e_email", cardinality="single"),
                _spec("NAME", "e_name", cardinality="single"),
            ],
        )
        columns = await _columns(engine, schema, "subject")
        assert "email" in columns and "name" in columns

    async def test_schema_without_document_entities_skipped(self, engine, setup_database):
        name = f"tenant_legacy_{uuid.uuid4().hex[:8]}"
        await _make_schema(engine, name, with_document_entities=False)
        try:
            statements = await _reconcile(engine, name, [_spec("SKILL", "e_skill")])
            assert statements == []
            assert "subject" not in await _tables(engine, name)
        finally:
            await _drop_schema(engine, name)

    async def test_no_definitions_still_gets_subject(self, engine, schema):
        await _reconcile(engine, schema, [])
        assert "subject" in await _tables(engine, schema)
        assert await _columns(engine, schema, "subject") == ["document_id", "filename"]

        doc_id = str(uuid.uuid4())
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f'INSERT INTO "{schema}".subject (document_id, filename) '
                    "VALUES (:id, 'cv.pdf')"
                ),
                {"id": doc_id},
            )
            rows = await conn.execute(text(f'SELECT document_id FROM "{schema}".subject'))
        assert [r[0] for r in rows.fetchall()] == [doc_id]

    async def test_second_run_changes_nothing(self, engine, schema):
        definitions = [
            _spec("SKILL", "e_skill"),
            _spec("EMAIL", "e_email", cardinality="single"),
        ]
        first = await _reconcile(engine, schema, definitions)
        tables_after_first = await _tables(engine, schema)
        subject_after_first = await _columns(engine, schema, "subject")

        second = await _reconcile(engine, schema, definitions)
        assert second == first
        assert await _tables(engine, schema) == tables_after_first
        assert await _columns(engine, schema, "subject") == subject_after_first

    async def test_definition_without_identifier_is_skipped(self, engine, schema):
        # A NULL `sql_identifier` is a legitimate state for a row created before `037`'s
        # backfill. Slugging at read time would be non-deterministic across processes.
        statements = await _reconcile(engine, schema, [_spec("SKILL", None)])
        assert "subject" in await _tables(engine, schema)
        assert not any("e_skill" in s for s in statements)

    async def test_sync_and_async_executors_apply_the_same_ddl(self, engine, schema, sync_engine):
        definitions = [
            _spec("SKILL", "e_skill"),
            _spec("EMAIL", "e_email", cardinality="single"),
        ]
        async_statements = await _reconcile(engine, schema, definitions)

        # The extraction worker holds a sync Connection and gateway holds an AsyncSession; both
        # must apply byte-identical DDL or the worker projects into a shape the API never made.
        with sync_engine.begin() as conn:
            sync_statements = reconcile_entity_tables_sync(conn, schema, definitions)
        assert sync_statements == async_statements


@pytest.mark.asyncio
class TestNothingIsEverDropped:
    """verification.md rows 65, 68 — the never-drop rule against a live server."""

    async def test_deactivated_definition_keeps_its_table_and_rows(self, engine, schema):
        doc_id = str(uuid.uuid4())
        await _reconcile(engine, schema, [_spec("SKILL", "e_skill")])
        await _insert_child_row(engine, schema, "e_skill", doc_id, "python")
        assert await _row_count(engine, schema, "e_skill") == 1

        statements = await _reconcile(engine, schema, [_spec("SKILL", "e_skill", is_active=False)])

        assert "e_skill" in await _tables(engine, schema)
        assert await _row_count(engine, schema, "e_skill") == 1
        assert not any("DROP" in s.upper() for s in statements)

    async def test_reactivation_finds_the_retained_rows(self, engine, schema):
        doc_id = str(uuid.uuid4())
        await _reconcile(engine, schema, [_spec("SKILL", "e_skill")])
        await _insert_child_row(engine, schema, "e_skill", doc_id, "python")

        await _reconcile(engine, schema, [_spec("SKILL", "e_skill", is_active=False)])
        await _reconcile(engine, schema, [_spec("SKILL", "e_skill")])

        assert await _row_count(engine, schema, "e_skill") == 1

    async def test_deleted_definition_leaves_an_orphaned_table_in_place(self, engine, schema):
        doc_id = str(uuid.uuid4())
        await _reconcile(engine, schema, [_spec("SKILL", "e_skill")])
        await _insert_child_row(engine, schema, "e_skill", doc_id, "python")

        # The definition is gone from the catalog entirely, not merely deactivated — the only
        # signal is its absence from the list. Removing a genuinely dead table is a manual
        # operator action, so the reconciler logs it and moves on.
        statements = await _reconcile(engine, schema, [])

        assert "e_skill" in await _tables(engine, schema)
        assert await _row_count(engine, schema, "e_skill") == 1
        assert not any("DROP" in s.upper() for s in statements)

    async def test_orphaned_table_is_logged(self, engine, schema, caplog):
        await _reconcile(engine, schema, [_spec("SKILL", "e_skill")])
        with caplog.at_level("INFO", logger="src.shared.entity_views"):
            await _reconcile(engine, schema, [])
        assert any("orphaned" in record.message and "e_skill" in record.getMessage()
                   for record in caplog.records)

    async def test_cardinality_flip_keeps_both_representations(self, engine, schema):
        doc_id = str(uuid.uuid4())
        await _reconcile(engine, schema, [_spec("EMAIL", "e_email")])
        await _insert_child_row(engine, schema, "e_email", doc_id, "a@example.com")

        await _reconcile(engine, schema, [_spec("EMAIL", "e_email", cardinality="single")])

        # The child table and its rows survive; the subject column is added beside them and
        # starts NULL until the document is re-extracted.
        assert "e_email" in await _tables(engine, schema)
        assert await _row_count(engine, schema, "e_email") == 1
        assert "email" in await _columns(engine, schema, "subject")

        # And the reverse leaves the column in place.
        await _reconcile(engine, schema, [_spec("EMAIL", "e_email")])
        assert "email" in await _columns(engine, schema, "subject")

    async def test_flip_to_single_takes_the_child_table_off_the_query_surface(
        self, engine, schema
    ):
        doc_id = str(uuid.uuid4())
        await _reconcile(engine, schema, [_spec("EMAIL", "e_email")])
        await _insert_child_row(engine, schema, "e_email", doc_id, "a@example.com")

        as_single = [_spec("EMAIL", "e_email", cardinality="single")]
        statements = await _reconcile(engine, schema, as_single)

        # Retained on disk with its history, and no longer queryable. The projection stops
        # writing to it at the flip, so leaving it on the surface would answer every question
        # about email with zero rows while the real value sits in `subject.email`.
        assert "e_email" in await _tables(engine, schema)
        assert await _row_count(engine, schema, "e_email") == 1
        assert not any("DROP" in s.upper() for s in statements)
        assert "e_email" not in generated_table_names(as_single)

    async def test_flip_to_single_does_not_recreate_the_child_table(self, engine, schema):
        # A tenant whose tables were never built while the definition was `multi` gets no child
        # table at all: the `subject` column is the whole representation. This is the half the
        # reconciler was already right about, asserted so it stays that way.
        statements = await _reconcile(
            engine, schema, [_spec("EMAIL", "e_email", cardinality="single")]
        )

        assert "e_email" not in await _tables(engine, schema)
        assert "email" in await _columns(engine, schema, "subject")
        assert not any("e_email" in s for s in statements)

    async def test_off_surface_table_is_logged(self, engine, schema, caplog):
        await _reconcile(engine, schema, [_spec("EMAIL", "e_email")])
        with caplog.at_level("INFO", logger="src.shared.entity_views"):
            await _reconcile(engine, schema, [_spec("EMAIL", "e_email", cardinality="single")])

        # It is not an orphan — a definition still claims it — so the orphan line never names
        # it, and without this line the retained table is reported nowhere at all.
        assert any(
            "off_surface" in record.message and "e_email" in record.getMessage()
            for record in caplog.records
        )


@pytest.mark.asyncio
class TestSubjectColumnListChanges:
    """verification.md row 53 — the failure mode most likely to reach production."""

    async def test_added_single_extends_the_column_list_in_place(self, engine, schema):
        await _reconcile(engine, schema, [_spec("EMAIL", "e_email", cardinality="single")])
        assert await _columns(engine, schema, "subject") == ["document_id", "filename", "email"]

        doc_id = str(uuid.uuid4())
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f'INSERT INTO "{schema}".subject (document_id, filename, email) '
                    "VALUES (:id, 'cv.pdf', 'a@example.com')"
                ),
                {"id": doc_id},
            )

        await _reconcile(
            engine,
            schema,
            [
                _spec("EMAIL", "e_email", cardinality="single"),
                _spec("Full Name", "e_full_name", cardinality="single"),
            ],
        )
        assert await _columns(engine, schema, "subject") == [
            "document_id",
            "filename",
            "email",
            "full_name",
        ]

        # `ADD COLUMN IF NOT EXISTS` with no default is metadata-only: the existing row keeps
        # its values and the new column reads NULL.
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(f'SELECT email, full_name FROM "{schema}".subject WHERE document_id = :id'),
                    {"id": doc_id},
                )
            ).fetchone()
        assert tuple(row) == ("a@example.com", None)

    async def test_removed_single_keeps_its_column(self, engine, schema):
        await _reconcile(
            engine,
            schema,
            [
                _spec("EMAIL", "e_email", cardinality="single"),
                _spec("NAME", "e_name", cardinality="single"),
            ],
        )
        await _reconcile(engine, schema, [_spec("EMAIL", "e_email", cardinality="single")])
        # Dropping the column would destroy every already-projected value for a flag that
        # `toggle_entity_type` flips both ways.
        assert await _columns(engine, schema, "subject") == [
            "document_id",
            "filename",
            "email",
            "name",
        ]

    async def test_typed_single_gets_the_declared_column_type(self, engine, schema):
        await _reconcile(
            engine,
            schema,
            [
                _spec("YOE", "e_yoe", cardinality="single", value_kind="duration"),
                _spec("Start Date", "e_start_date", cardinality="single", value_kind="date"),
                _spec("NAME", "e_name", cardinality="single"),
            ],
        )
        async with engine.begin() as conn:
            rows = await conn.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema = :s AND table_name = 'subject'"
                ),
                {"s": schema},
            )
        types = {r[0]: r[1] for r in rows.fetchall()}
        assert types["yoe"] == "double precision"
        assert types["start_date"] == "date"
        assert types["name"] == "text"


async def _column_types(engine, schema, table):
    async with engine.begin() as conn:
        rows = await conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t"
            ),
            {"s": schema, "t": table},
        )
    return {r[0]: r[1] for r in rows.fetchall()}


async def _subject_row(engine, schema, document_id="doc-1", **columns):
    names = ["document_id", *columns]
    placeholders = ", ".join(f":{name}" for name in names)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f'INSERT INTO "{schema}".{SUBJECT_TABLE_NAME} ({", ".join(names)}) '
                f"VALUES ({placeholders}) "
                "ON CONFLICT (document_id) DO NOTHING"
            ),
            {"document_id": document_id, **columns},
        )


@pytest.mark.asyncio
class TestSubjectColumnTypeConverges:
    """verification.md rows 1-8, 11, 12.

    A `value_kind` edit changes the catalog; `ADD COLUMN IF NOT EXISTS` changes nothing. Every
    consumer then trusts the catalog — the projection writes the representation the new kind
    implies, and the query surface declares the new type to the SQL generator — while the column
    is still the old type. Found live: `PHONE_NUMBER` declared `number` over a `TEXT` column,
    and the projection stored `'7708888801.0'` for an extracted `'7708888801'`.
    """

    async def test_text_to_number_converges(self, engine, schema):
        """Row 1."""
        await _reconcile(engine, schema, [_spec("PHONE", "e_phone", cardinality="single")])
        assert (await _column_types(engine, schema, "subject"))["phone"] == "text"

        await _reconcile(
            engine, schema,
            [_spec("PHONE", "e_phone", cardinality="single", value_kind="number")],
        )

        assert (await _column_types(engine, schema, "subject"))["phone"] == "double precision"

    async def test_number_to_text_converges(self, engine, schema):
        """Row 2 — the direction that fixes the observed `PHONE_NUMBER` misconfiguration."""
        await _reconcile(
            engine, schema,
            [_spec("PHONE", "e_phone", cardinality="single", value_kind="number")],
        )
        assert (await _column_types(engine, schema, "subject"))["phone"] == "double precision"

        await _reconcile(engine, schema, [_spec("PHONE", "e_phone", cardinality="single")])

        assert (await _column_types(engine, schema, "subject"))["phone"] == "text"

    async def test_text_to_date_and_back(self, engine, schema):
        """Rows 1, 2 over the date type."""
        await _reconcile(engine, schema, [_spec("START", "e_start", cardinality="single")])

        await _reconcile(
            engine, schema,
            [_spec("START", "e_start", cardinality="single", value_kind="date")],
        )
        assert (await _column_types(engine, schema, "subject"))["start"] == "date"

        await _reconcile(engine, schema, [_spec("START", "e_start", cardinality="single")])
        assert (await _column_types(engine, schema, "subject"))["start"] == "text"

    async def test_number_and_date_converge_though_no_cast_exists(self, engine, schema):
        """Row 3 — PostgreSQL provides no cast in either direction between these two, which is
        why the conversion clears the column rather than converting it."""
        await _reconcile(
            engine, schema,
            [_spec("MOMENT", "e_moment", cardinality="single", value_kind="number")],
        )

        await _reconcile(
            engine, schema, [_spec("MOMENT", "e_moment", cardinality="single", value_kind="date")]
        )
        assert (await _column_types(engine, schema, "subject"))["moment"] == "date"

        await _reconcile(
            engine, schema, [_spec("MOMENT", "e_moment", cardinality="single", value_kind="number")]
        )
        assert (await _column_types(engine, schema, "subject"))["moment"] == "double precision"

    async def test_unconvertible_data_does_not_block_the_change(self, engine, schema):
        """Row 4 — `'unknown'` would abort any casting conversion, and with it the admin's edit
        or the extraction run that triggered the reconcile."""
        await _reconcile(engine, schema, [_spec("YOE", "e_yoe", cardinality="single")])
        await _subject_row(engine, schema, "doc-1", yoe="unknown")
        await _subject_row(engine, schema, "doc-2", yoe="5 years")

        await _reconcile(
            engine, schema,
            [_spec("YOE", "e_yoe", cardinality="single", value_kind="number")],
        )

        assert (await _column_types(engine, schema, "subject"))["yoe"] == "double precision"

    async def test_the_column_is_cleared_and_the_rows_survive(self, engine, schema):
        """Row 8 — the values go, the rows stay. `'5 years'` is not `5.0`, and no cast makes it
        so; the projection re-derives the column from the entity store at re-extraction."""
        await _reconcile(engine, schema, [_spec("YOE", "e_yoe", cardinality="single")])
        await _subject_row(engine, schema, "doc-1", yoe="5 years")

        await _reconcile(
            engine, schema,
            [_spec("YOE", "e_yoe", cardinality="single", value_kind="number")],
        )

        async with engine.begin() as conn:
            rows = await conn.execute(
                text(f'SELECT document_id, yoe FROM "{schema}".{SUBJECT_TABLE_NAME}')
            )
        assert [tuple(r) for r in rows.fetchall()] == [("doc-1", None)]

    async def test_the_entity_store_is_untouched(self, engine, schema):
        """Row 7 — `document_entities` is the system of record and keeps every value, which is
        what makes clearing the derived column safe."""
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f'INSERT INTO "{schema}".document_entities '
                    "(id, document_id, entity_type, entity_value, normalized_value, confidence) "
                    "VALUES ('e1', 'doc-1', 'YOE', '5 years', '5 years', 0.9)"
                )
            )
        before = await _column_types(engine, schema, "document_entities")

        await _reconcile(engine, schema, [_spec("YOE", "e_yoe", cardinality="single")])
        await _reconcile(
            engine, schema,
            [_spec("YOE", "e_yoe", cardinality="single", value_kind="number")],
        )

        async with engine.begin() as conn:
            rows = await conn.execute(
                text(f'SELECT entity_value FROM "{schema}".document_entities')
            )
        assert [r[0] for r in rows.fetchall()] == ["5 years"]
        assert await _column_types(engine, schema, "document_entities") == before

    async def test_an_unchanged_schema_emits_no_type_statement(self, engine, schema):
        """Row 5 — and the guard on Risk 1: a spelling mismatch would retype every column on
        every run, blanking the whole surface each time."""
        definitions = [
            _spec("YOE", "e_yoe", cardinality="single", value_kind="duration"),
            _spec("START", "e_start", cardinality="single", value_kind="date"),
            _spec("NAME", "e_name", cardinality="single"),
        ]
        await _reconcile(engine, schema, definitions)
        await _subject_row(engine, schema, "doc-1", name="Reshma U")

        statements = await _reconcile(engine, schema, definitions)

        assert [s for s in statements if "ALTER COLUMN" in s] == []
        async with engine.begin() as conn:
            kept = await conn.execute(text(f'SELECT name FROM "{schema}".{SUBJECT_TABLE_NAME}'))
        assert kept.scalar() == "Reshma U"

    async def test_a_newly_created_column_is_not_also_retyped(self, engine, schema):
        """Row 6 — the ordering guard from design Decision 1: a column created in this run is
        created at the declared type and must not be blanked by a convergence in the same list."""
        statements = await _reconcile(
            engine, schema,
            [_spec("YOE", "e_yoe", cardinality="single", value_kind="number")],
        )

        assert any("ADD COLUMN IF NOT EXISTS yoe" in s for s in statements)
        assert [s for s in statements if "ALTER COLUMN" in s] == []
        assert (await _column_types(engine, schema, "subject"))["yoe"] == "double precision"

    async def test_convergence_follows_the_add_column_statements(self, engine, schema):
        """The same ordering, asserted on a schema that both gains a column and converges one."""
        await _reconcile(engine, schema, [_spec("YOE", "e_yoe", cardinality="single")])

        statements = await _reconcile(
            engine, schema,
            [
                _spec("YOE", "e_yoe", cardinality="single", value_kind="number"),
                _spec("NAME", "e_name", cardinality="single"),
            ],
        )

        added = next(i for i, s in enumerate(statements) if "ADD COLUMN IF NOT EXISTS name" in s)
        retyped = next(i for i, s in enumerate(statements) if "ALTER COLUMN yoe" in s)
        assert added < retyped

    async def test_a_deactivated_definitions_column_keeps_its_type_and_values(
        self, engine, schema
    ):
        """Row 11 — off the surface is off the surface: nothing writes it, nothing queries it,
        and its rows are the only copy of that projection."""
        await _reconcile(engine, schema, [_spec("YOE", "e_yoe", cardinality="single")])
        await _subject_row(engine, schema, "doc-1", yoe="5 years")

        await _reconcile(
            engine, schema,
            [_spec("YOE", "e_yoe", cardinality="single", value_kind="number", is_active=False)],
        )

        assert (await _column_types(engine, schema, "subject"))["yoe"] == "text"
        async with engine.begin() as conn:
            kept = await conn.execute(text(f'SELECT yoe FROM "{schema}".{SUBJECT_TABLE_NAME}'))
        assert kept.scalar() == "5 years"

    async def test_reactivating_with_a_changed_kind_converges(self, engine, schema):
        """Row 12 — the column rejoins the surface, and the invariant applies again at that
        moment."""
        await _reconcile(engine, schema, [_spec("YOE", "e_yoe", cardinality="single")])
        await _reconcile(
            engine, schema,
            [_spec("YOE", "e_yoe", cardinality="single", value_kind="number", is_active=False)],
        )
        assert (await _column_types(engine, schema, "subject"))["yoe"] == "text"

        await _reconcile(
            engine, schema,
            [_spec("YOE", "e_yoe", cardinality="single", value_kind="number")],
        )

        assert (await _column_types(engine, schema, "subject"))["yoe"] == "double precision"

    async def test_the_phone_number_regression(self, engine, schema):
        """The observed instance, end to end: a `TEXT` column, a catalog changed to `number`,
        one reconcile. The system must not remain mismatched."""
        await _reconcile(
            engine, schema, [_spec("PHONE_NUMBER", "e_phone_number", cardinality="single")]
        )
        await _subject_row(engine, schema, "doc-1", phone_number="7708888801")

        definitions = [
            _spec("PHONE_NUMBER", "e_phone_number", cardinality="single", value_kind="number")
        ]
        await _reconcile(engine, schema, definitions)

        types = await _column_types(engine, schema, "subject")
        declared = {c: t for _d, c, t in subject_columns(definitions)}
        assert types["phone_number"] == "double precision"
        assert declared["phone_number"] == "DOUBLE PRECISION"
        # And back again, which is the correction that was applied by hand.
        await _reconcile(
            engine, schema, [_spec("PHONE_NUMBER", "e_phone_number", cardinality="single")]
        )
        assert (await _column_types(engine, schema, "subject"))["phone_number"] == "text"

    async def test_the_convergence_is_logged_with_both_types(self, engine, schema, caplog):
        """Row 8 — a cleared column is otherwise discovered later with nothing to attribute it
        to."""
        import logging

        await _reconcile(engine, schema, [_spec("YOE", "e_yoe", cardinality="single")])

        with caplog.at_level(logging.WARNING, logger="src.shared.entity_views"):
            await _reconcile(
                engine, schema,
                [_spec("YOE", "e_yoe", cardinality="single", value_kind="number")],
            )

        line = next(m for m in caplog.messages if "column_retyped" in m)
        assert "column=yoe" in line
        assert "from=text" in line
        assert "to=DOUBLE PRECISION" in line
        assert "values_cleared=true" in line

    async def test_the_sync_executor_converges_identically(self, engine, schema, sync_engine):
        """Both executors share one plan; only `execute` differs. The worker reconciles at run
        start, so it meets a diverged column before any document is projected."""
        await _reconcile(engine, schema, [_spec("YOE", "e_yoe", cardinality="single")])

        with sync_engine.begin() as conn:
            reconcile_entity_tables_sync(
                conn, schema,
                [_spec("YOE", "e_yoe", cardinality="single", value_kind="date")],
            )

        assert (await _column_types(engine, schema, "subject"))["yoe"] == "date"

    async def test_duration_still_declares_double_precision(self, engine, schema):
        """`duration` is unchanged by this work — it keeps its unit normalisation and its
        column type."""
        await _reconcile(
            engine, schema,
            [_spec("YOE", "e_yoe", cardinality="single", value_kind="duration")],
        )

        assert (await _column_types(engine, schema, "subject"))["yoe"] == "double precision"
