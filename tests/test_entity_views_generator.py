"""Pure-function tests for the generated entity table layer.

Every test in this file runs without a database. That is the point of the
`build_role_statements`-style contract the generator follows: the failure modes of generated
DDL are silent (a missing projection returns zero rows, not an error), so the statements have
to be assertable directly rather than only observable through their effects.

Covers verification.md rows 39-58, 69, 70.
"""

import re
from types import SimpleNamespace

import pytest

from src.shared.entity_views import (
    CHILD_VALUE_COLUMNS,
    GENERATED_IDENTIFIER_RE,
    SUBJECT_TABLE_NAME,
    EntityDefinitionSpec,
    InvalidIdentifierError,
    build_child_table_statements,
    build_entity_table_statements,
    build_subject_column_type_statements,
    build_subject_table_statements,
    catalogued_table_names,
    diverging_subject_columns,
    entity_type_literals,
    expected_table_names,
    generated_table_names,
    resolve_generated_tables,
    resolve_query_surface,
    subject_columns,
    to_sql_identifier,
)

SCHEMA = "tenant_acme"

_LITERAL_RE = re.compile(r"'(?:[^']|'')*'")

# Anything that could destroy a row or a relation. Asserted against the whole generated script
# rather than against the statements a particular definition set happens to produce, because
# the rule is "this module never emits one", not "it does not emit one today".
DESTRUCTIVE_KEYWORDS = ("DROP TABLE", "DROP VIEW", "DROP COLUMN", "DELETE", "TRUNCATE")


def _outside_literals(sql: str) -> str:
    """The statement with every single-quoted literal removed.

    Injection is about what the server *executes*, not about what characters appear anywhere in
    the string."""
    return _LITERAL_RE.sub("''", sql)


def _spec(name, identifier, **kwargs):
    return EntityDefinitionSpec(name=name, sql_identifier=identifier, **kwargs)


class TestToSqlIdentifier:
    """verification.md rows 39-42"""

    def test_punctuation_slugged(self):
        assert to_sql_identifier("Skills & Tools", set()) == "e_skills_tools"

    def test_reserved_word_prefixed(self):
        identifier = to_sql_identifier("select", set())
        assert identifier == "e_select"
        # The prefix is what makes the result usable unquoted; a bare `select` would be a
        # syntax error at every use site.
        assert GENERATED_IDENTIFIER_RE.fullmatch(identifier)

    def test_leading_digit_valid(self):
        identifier = to_sql_identifier("2024 Revenue", set())
        assert identifier == "e_2024_revenue"
        assert GENERATED_IDENTIFIER_RE.fullmatch(identifier)

    def test_overlong_truncated_before_suffix(self):
        long_name = "a" * 200
        first = to_sql_identifier(long_name, set())
        assert len(first) == 63

        second = to_sql_identifier(long_name, {first})
        assert len(second) <= 63
        assert second != first
        assert GENERATED_IDENTIFIER_RE.fullmatch(second)

    def test_collisions_deterministic(self):
        def slug_sequence():
            taken: set[str] = set()
            results = []
            for name in ("Vendor Name", "vendor-name"):
                identifier = to_sql_identifier(name, taken)
                taken.add(identifier)
                results.append(identifier)
            return results

        first_run = slug_sequence()
        assert first_run[0] != first_run[1]
        assert first_run == ["e_vendor_name", "e_vendor_name_2"]
        assert slug_sequence() == first_run

    @pytest.mark.parametrize("name", ["", "---", "   ", "日本語", "🙂", None])
    def test_degenerate_input_fallback(self, name):
        identifier = to_sql_identifier(name, set())
        assert GENERATED_IDENTIFIER_RE.fullmatch(identifier)
        assert identifier == "e_unnamed"

    def test_degenerate_inputs_still_collision_resolve(self):
        # Two entity types that both slug to nothing must not both claim `e_unnamed`.
        first = to_sql_identifier("---", set())
        second = to_sql_identifier("日本語", {first})
        assert second == "e_unnamed_2"

    def test_accents_are_folded_not_dropped(self):
        assert to_sql_identifier("Café Región", set()) == "e_cafe_region"

    def test_injection_name_inert(self):
        identifier = to_sql_identifier('"; DROP TABLE documents; --', set())
        assert GENERATED_IDENTIFIER_RE.fullmatch(identifier)
        # No quote, semicolon, or comment marker survives the character class.
        assert not set(identifier) & set("\"';-")


def test_generated_identifier_grammar_is_total():
    """Any input at all must produce something the grammar accepts."""
    hostile = [
        "",
        " ",
        "\n\t",
        "'" * 10,
        "a" * 500,
        "1",
        "_",
        "__leading_and_trailing__",
        "MiXeD CaSe",
        "tab\tseparated",
        "null\x00byte",
        "SELECT * FROM pg_authid",
    ]
    taken: set[str] = set()
    for name in hostile:
        identifier = to_sql_identifier(name, taken)
        assert GENERATED_IDENTIFIER_RE.fullmatch(identifier), name
        assert len(identifier) <= 63
        assert identifier not in taken
        taken.add(identifier)


class TestPureGeneration:
    """verification.md rows 43, 45"""

    def test_no_database_required(self):
        # Nothing in this call opens a connection, reads settings, or imports a service
        # package. If that ever changes this test fails at import or call time, not later in
        # production.
        statements = build_entity_table_statements(
            SCHEMA, [_spec("SKILL", "e_skill"), _spec("EMAIL", "e_email", cardinality="single")]
        )
        assert statements
        assert all(isinstance(statement, str) for statement in statements)

    def test_generation_idempotent(self):
        definitions = [
            _spec("SKILL", "e_skill"),
            _spec("EMAIL", "e_email", cardinality="single"),
            _spec("Employer", "e_employer", base_label_mapping={"ORG": "Employer"}),
        ]
        assert build_entity_table_statements(
            SCHEMA, definitions
        ) == build_entity_table_statements(SCHEMA, definitions)

    def test_generation_order_independent_of_input_order(self):
        definitions = [_spec("SKILL", "e_skill"), _spec("EMAIL", "e_email", cardinality="single")]
        assert build_entity_table_statements(
            SCHEMA, definitions
        ) == build_entity_table_statements(SCHEMA, list(reversed(definitions)))

    @pytest.mark.parametrize(
        "schema", ["tenant acme", "tenant-acme", "", "tenant_acme; DROP TABLE documents", '"x"']
    )
    def test_invalid_schema_raises(self, schema):
        with pytest.raises(InvalidIdentifierError):
            build_entity_table_statements(schema, [_spec("SKILL", "e_skill")])

    def test_invalid_sql_identifier_raises(self):
        with pytest.raises(InvalidIdentifierError):
            build_entity_table_statements(SCHEMA, [_spec("SKILL", "Skills & Tools")])

    def test_every_statement_is_rerunnable(self):
        definitions = [
            _spec("SKILL", "e_skill"),
            _spec("EMAIL", "e_email", cardinality="single"),
        ]
        for statement in build_entity_table_statements(SCHEMA, definitions):
            if statement.startswith("CREATE TABLE"):
                assert statement.startswith("CREATE TABLE IF NOT EXISTS")
            elif statement.startswith("CREATE INDEX"):
                assert statement.startswith("CREATE INDEX IF NOT EXISTS")
            elif statement.startswith("ALTER TABLE"):
                assert "ADD COLUMN IF NOT EXISTS" in statement
            else:
                pytest.fail(f"unexpected statement kind: {statement}")


class TestNoDestructiveStatement:
    """verification.md rows 43, 69, 70 — the never-drop rule, asserted rather than reviewed."""

    @pytest.mark.parametrize(
        "definitions",
        [
            [],
            [_spec("SKILL", "e_skill")],
            [_spec("SKILL", "e_skill", is_active=False)],
            [_spec("EMAIL", "e_email", cardinality="single", is_active=False)],
            [
                _spec("SKILL", "e_skill"),
                _spec("EMAIL", "e_email", cardinality="single"),
                _spec("OLD", "e_old", is_active=False),
                _spec("NO_IDENTIFIER", None),
            ],
        ],
    )
    def test_no_destructive_statement_is_ever_emitted(self, definitions):
        for statement in build_entity_table_statements(SCHEMA, definitions):
            residue = _outside_literals(statement).upper()
            for forbidden in DESTRUCTIVE_KEYWORDS:
                assert forbidden not in residue, statement

    def test_subject_is_never_dropped(self):
        # The view design dropped and recreated `subject` on every column-list change. A table
        # is extended in place instead, so no reader ever observes a missing relation.
        statements = build_entity_table_statements(
            SCHEMA, [_spec("EMAIL", "e_email", cardinality="single")]
        )
        assert not any("DROP" in s.upper() for s in statements)

    def test_inactive_definition_is_left_alone_not_dropped(self):
        # `is_active` is reversible — `toggle_entity_type` flips it both ways — so a drop here
        # would turn an undo into data loss.
        statements = build_entity_table_statements(
            SCHEMA, [_spec("SKILL", "e_skill", is_active=False)]
        )
        assert not any("e_skill" in s for s in statements)
        assert not any("DROP" in s.upper() for s in statements)

    def test_module_exports_no_drop_builder(self):
        import src.shared.entity_views as entity_views

        assert not hasattr(entity_views, "build_drop_view_statements")


class TestChildTables:
    """verification.md rows 44, 46, 47"""

    def _child_create(self, definition):
        return build_child_table_statements(SCHEMA, definition)[0]

    def test_single_multi_definition(self):
        create = self._child_create(_spec("SKILL", "e_skill"))
        assert create.startswith(f"CREATE TABLE IF NOT EXISTS {SCHEMA}.e_skill")
        assert "PRIMARY KEY (document_id, normalized_value)" in create

    def test_index_on_normalized_value(self):
        statements = build_child_table_statements(SCHEMA, _spec("SKILL", "e_skill"))
        assert (
            "CREATE INDEX IF NOT EXISTS idx_e_skill_normalized_value "
            f"ON {SCHEMA}.e_skill (normalized_value)" in statements
        )

    def test_three_multi_definitions_get_three_tables(self):
        definitions = [
            _spec("SKILL", "e_skill"),
            _spec("EMPLOYER", "e_employer"),
            _spec("CERT", "e_cert"),
        ]
        statements = build_entity_table_statements(SCHEMA, definitions)
        creates = [
            s
            for s in statements
            if s.startswith("CREATE TABLE IF NOT EXISTS") and SUBJECT_TABLE_NAME not in s
        ]
        assert len(creates) == 3
        assert {"e_cert", "e_employer", "e_skill"} == {
            s.split(f"{SCHEMA}.")[1].split(" ")[0] for s in creates
        }

    @pytest.mark.parametrize(
        "value_kind", [None, "text", "number", "money", "duration", "boolean", "date"]
    )
    def test_column_list_does_not_vary_with_value_kind(self, value_kind):
        # A fixed shape means a new `value_kind` never forces an ALTER on a populated child
        # table: the column is already there and stays NULL.
        baseline = self._child_create(_spec("A", "e_a"))
        variant = self._child_create(_spec("A", "e_a", value_kind=value_kind))
        assert baseline == variant

    def test_every_typed_column_is_present(self):
        create = self._child_create(_spec("SKILL", "e_skill"))
        for column in (
            "document_id VARCHAR NOT NULL",
            "value TEXT NOT NULL",
            "normalized_value TEXT NOT NULL",
            "value_number DOUBLE PRECISION",
            "value_number_high DOUBLE PRECISION",
            "value_date DATE",
            "value_date_high DATE",
            "value_unit TEXT",
            "confidence DOUBLE PRECISION NOT NULL",
            "page_number INTEGER",
            "occurrence_count INTEGER NOT NULL DEFAULT 1",
        ):
            assert column in create

    def test_no_foreign_key_to_documents(self):
        # Integrity comes from delete propagation instead: a FK would make the document-delete
        # path order-dependent and take a lock the EAV table does not.
        create = self._child_create(_spec("SKILL", "e_skill"))
        assert "REFERENCES" not in create.upper()


class TestSubjectTable:
    """verification.md rows 48-52"""

    def test_subject_table_is_created(self):
        statements = build_subject_table_statements(SCHEMA, [])
        assert statements[0] == (
            f"CREATE TABLE IF NOT EXISTS {SCHEMA}.{SUBJECT_TABLE_NAME} (\n"
            "    document_id VARCHAR PRIMARY KEY,\n"
            "    filename TEXT\n"
            ")"
        )

    def test_single_definition_becomes_a_column(self):
        statements = build_subject_table_statements(
            SCHEMA, [_spec("EMAIL", "e_email", cardinality="single")]
        )
        assert (
            f"ALTER TABLE {SCHEMA}.{SUBJECT_TABLE_NAME} "
            "ADD COLUMN IF NOT EXISTS email TEXT" in statements
        )

    def test_zero_singles_still_yields_subject(self):
        statements = build_subject_table_statements(SCHEMA, [_spec("SKILL", "e_skill")])
        assert len(statements) == 1
        assert "ADD COLUMN" not in statements[0]

    @pytest.mark.parametrize("value_kind", ["number", "money", "duration", "boolean"])
    def test_numeric_kinds_get_double_precision(self, value_kind):
        statements = build_subject_table_statements(
            SCHEMA,
            [
                _spec(
                    "Years Experience",
                    "e_years_experience",
                    cardinality="single",
                    value_kind=value_kind,
                )
            ],
        )
        assert (
            f"ALTER TABLE {SCHEMA}.{SUBJECT_TABLE_NAME} "
            "ADD COLUMN IF NOT EXISTS years_experience DOUBLE PRECISION" in statements
        )

    def test_typed_single_gets_exactly_one_column(self):
        # The view design projected a `<name>_text` companion beside every typed column. The
        # surface text is one join away in `document_entities`, and doubling the column count
        # doubles what every prompt has to describe.
        statements = build_subject_table_statements(
            SCHEMA,
            [_spec("Years Experience", "e_years_experience", cardinality="single", value_kind="number")],
        )
        adds = [s for s in statements if "ADD COLUMN" in s]
        assert len(adds) == 1
        assert "years_experience_text" not in "\n".join(statements)

    def test_date_kind_gets_a_date_column(self):
        statements = build_subject_table_statements(
            SCHEMA, [_spec("Start Date", "e_start_date", cardinality="single", value_kind="date")]
        )
        assert (
            f"ALTER TABLE {SCHEMA}.{SUBJECT_TABLE_NAME} "
            "ADD COLUMN IF NOT EXISTS start_date DATE" in statements
        )

    @pytest.mark.parametrize("value_kind", [None, "text", "something_new"])
    def test_unknown_and_text_kinds_get_text(self, value_kind):
        statements = build_subject_table_statements(
            SCHEMA, [_spec("NAME", "e_name", cardinality="single", value_kind=value_kind)]
        )
        assert (
            f"ALTER TABLE {SCHEMA}.{SUBJECT_TABLE_NAME} "
            "ADD COLUMN IF NOT EXISTS name TEXT" in statements
        )

    @pytest.mark.parametrize("identifier", ["e_filename", "e_document_id"])
    def test_identity_column_collision_disambiguated(self, identifier):
        statements = build_subject_table_statements(
            SCHEMA, [_spec("X", identifier, cardinality="single")]
        )
        added = [s.split("ADD COLUMN IF NOT EXISTS ")[1].split(" ")[0] for s in statements[1:]]
        assert added and added[0] not in ("document_id", "filename")

    def test_pivot_columns_never_collide_with_each_other(self):
        statements = build_subject_table_statements(
            SCHEMA,
            [
                _spec("A", "e_x", cardinality="single", value_kind="number"),
                _spec("B", "e_x_2", cardinality="single"),
            ],
        )
        added = [s.split("ADD COLUMN IF NOT EXISTS ")[1].split(" ")[0] for s in statements[1:]]
        assert len(added) == len(set(added)), added

    def test_inactive_single_gets_no_column(self):
        statements = build_subject_table_statements(
            SCHEMA, [_spec("EMAIL", "e_email", cardinality="single", is_active=False)]
        )
        assert len(statements) == 1


class TestEntityTypeLiterals:
    """verification.md rows 54-58"""

    def test_is_public(self):
        import src.shared.entity_views as entity_views

        assert callable(getattr(entity_views, "entity_type_literals", None))

    def test_stored_case_differing_from_definition_case_still_matches(self):
        assert entity_type_literals(_spec("Skill", "e_skill")) == ["SKILL"]

    def test_base_label_is_included(self):
        literals = entity_type_literals(
            _spec("Employer", "e_employer", base_label_mapping={"ORG": ["employer"]})
        )
        assert literals == ["EMPLOYER", "ORG"]

    @pytest.mark.parametrize("mapping", [None, {}])
    def test_no_mapping_yields_the_name_alone(self, mapping):
        assert entity_type_literals(
            _spec("Skill", "e_skill", base_label_mapping=mapping)
        ) == ["SKILL"]

    def test_deterministically_ordered(self):
        first = entity_type_literals(
            _spec("E", "e_e", base_label_mapping={"ORG": 1, "PER": 1, "MISC": 1})
        )
        second = entity_type_literals(
            _spec("E", "e_e", base_label_mapping={"PER": 1, "MISC": 1, "ORG": 1})
        )
        assert first == second == sorted(first)

    def test_nameless_definition_yields_mapping_only(self):
        assert entity_type_literals(_spec("", "e_x", base_label_mapping={"ORG": 1})) == ["ORG"]


class TestGeneratedTableNames:
    """verification.md rows 66, 98, 99 — the set fed to grants and to `validate_sql`."""

    def test_active_multi_definitions_and_subject(self):
        names = generated_table_names([_spec("SKILL", "e_skill"), _spec("TOOL", "e_tool")])
        assert names == {SUBJECT_TABLE_NAME, "e_skill", "e_tool"}

    def test_single_definition_contributes_a_column_not_a_table(self):
        definitions = [_spec("EMAIL", "e_email", cardinality="single")]
        # Its values are reachable, as a `subject` column. `e_email` names no relation the
        # reconciler maintains, so a query naming it must not validate.
        assert [column for _d, column, _t in subject_columns(definitions)] == ["email"]
        assert generated_table_names(definitions) == {SUBJECT_TABLE_NAME}

    def test_child_table_retained_from_a_multi_era_is_off_the_surface(self):
        # The regression this class exists for. `EMAIL` was `multi` when some reconcile ran, so
        # `e_email` is on disk and the never-drop rule keeps it there with its history. Nothing
        # has written to it since the flip, so exposing it answers every question about email
        # with zero rows while the real value sits in `subject.email`.
        assert "e_email" in generated_table_names([_spec("EMAIL", "e_email")])

        as_single = [_spec("EMAIL", "e_email", cardinality="single")]
        assert "e_email" not in generated_table_names(as_single)
        # Still claimed by a definition, so the reconciler must not call it an orphan either.
        assert "e_email" in catalogued_table_names(as_single)

    def test_inactive_definition_excluded(self):
        names = generated_table_names([_spec("SKILL", "e_skill", is_active=False)])
        assert names == {SUBJECT_TABLE_NAME}

    def test_unassigned_identifier_excluded(self):
        names = generated_table_names([_spec("SKILL", None)])
        assert names == {SUBJECT_TABLE_NAME}

    def test_surface_is_exactly_what_the_reconciler_maintains(self):
        # Asserted rather than reviewed: a table on the whitelist the reconciler never creates
        # is a query the validator accepts and the database refuses, and the reverse is a query
        # the validator rejects for a table the role can read. Neither is visible at run time.
        definitions = [
            _spec("SKILL", "e_skill"),
            _spec("EMAIL", "e_email", cardinality="single"),
            _spec("RETIRED", "e_retired", is_active=False),
            _spec("UNSLUGGED", None),
        ]
        assert generated_table_names(definitions) == expected_table_names(definitions)


class TestNoInjectableDDL:
    """verification.md rows 35, 36 applied to the DDL side."""

    HOSTILE_NAME = "; DROP TABLE documents; --"

    def test_hostile_name_produces_inert_ddl(self):
        identifier = to_sql_identifier(self.HOSTILE_NAME, set())
        definitions = [
            _spec(self.HOSTILE_NAME, identifier),
            _spec(self.HOSTILE_NAME, "e_x", cardinality="single"),
        ]
        for statement in build_entity_table_statements(SCHEMA, definitions):
            residue = _outside_literals(statement).upper()
            assert "DROP TABLE" not in residue
            assert ";" not in residue
            assert "--" not in residue

    def test_entity_names_never_reach_the_ddl_at_all(self):
        # The table layer no longer embeds an entity-type predicate, so tenant text has no
        # position in generated DDL — not even a quoted one.
        statements = build_entity_table_statements(
            SCHEMA, [_spec("O'Brien's ' type", "e_obrien")]
        )
        for statement in statements:
            assert "'" not in statement
            assert "O'Brien" not in statement


class _SurfaceResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return list(self._rows)


class _SurfaceSession:
    """Answers `_QUERY_SURFACE_QUERY` from canned `public.entity_definitions` rows.

    Rows are `SimpleNamespace`, not tuples, because the resolver reads them by column name —
    the same access the driver's `Row` provides."""

    def __init__(self, rows):
        self.rows = list(rows)
        self.statements: list[str] = []

    async def execute(self, statement, params=None):
        self.statements.append(str(statement))
        return _SurfaceResult(self.rows)


def _row(tenant_id, name, identifier, **kwargs):
    return SimpleNamespace(
        tenant_id=tenant_id,
        name=name,
        sql_identifier=identifier,
        cardinality=kwargs.get("cardinality", "multi"),
        value_kind=kwargs.get("value_kind"),
        value_unit=kwargs.get("value_unit"),
        description=kwargs.get("description"),
        examples=kwargs.get("examples"),
        is_active=kwargs.get("is_active", True),
        base_label_mapping=kwargs.get("base_label_mapping"),
    )


class TestQuerySurfaceResolver:
    """verification.md rows 66-71 — the one authoritative description of the readable surface."""

    async def test_reports_columns_with_declared_types(self):
        """Rows 66, 68 — identifiers alone are not enough; a consumer needs the types."""
        session = _SurfaceSession([
            _row("acme", "Years Experience", "e_years_experience",
                 cardinality="single", value_kind="number"),
            _row("acme", "Skill", "e_skill"),
        ])

        surface = (await resolve_query_surface(session, [SCHEMA]))[SCHEMA]

        assert surface.table_names == {SUBJECT_TABLE_NAME, "e_skill"}
        assert [(c.name, c.sql_type) for c in surface.subject_columns] == [
            ("years_experience", "DOUBLE PRECISION")
        ]
        assert set(surface.child_tables) == {"e_skill"}
        columns = surface.columns_by_relation()
        assert columns[SUBJECT_TABLE_NAME] == {"document_id", "filename", "years_experience"}
        assert columns["e_skill"] == set(CHILD_VALUE_COLUMNS)

    async def test_declared_type_needs_value_kind_from_the_query(self):
        """Row 68 — without `value_kind` on the row every column resolves TEXT, and a
        quantitative comparison against a TEXT column is a wrong answer, not an error."""
        session = _SurfaceSession([
            _row("acme", "Salary", "e_salary", cardinality="single", value_kind="money"),
            _row("acme", "Start Date", "e_start_date", cardinality="single", value_kind="date"),
            _row("acme", "Title", "e_title", cardinality="single"),
        ])

        surface = (await resolve_query_surface(session, [SCHEMA]))[SCHEMA]

        assert {c.name: c.sql_type for c in surface.subject_columns} == {
            "salary": "DOUBLE PRECISION",
            "start_date": "DATE",
            "title": "TEXT",
        }

    async def test_carries_description_and_examples(self):
        """Row 67 — the tenant-authored semantics travel with the relation."""
        session = _SurfaceSession([
            _row("acme", "Skill", "e_skill",
                 description="a technology or professional capability",
                 examples=["python", "kubernetes"]),
            _row("acme", "Email", "e_email", cardinality="single", description="work email"),
        ])

        surface = (await resolve_query_surface(session, [SCHEMA]))[SCHEMA]

        skill = surface.child_tables["e_skill"]
        assert skill.name == "Skill"
        assert skill.description == "a technology or professional capability"
        assert skill.examples == ["python", "kubernetes"]
        assert surface.subject_columns[0].definition.description == "work email"

    async def test_examples_parsed_from_json_text(self):
        """`examples` reads back as text on a TEXT column and as a list on JSONB."""
        session = _SurfaceSession([_row("acme", "Skill", "e_skill", examples='["python"]')])

        surface = (await resolve_query_surface(session, [SCHEMA]))[SCHEMA]

        assert surface.child_tables["e_skill"].examples == ["python"]

    async def test_off_surface_definitions_excluded_and_single_listed_as_column(self):
        """Row 69 — inactive, identifier-less, and `single`-retained tables stay off."""
        session = _SurfaceSession([
            _row("acme", "Skill", "e_skill"),
            _row("acme", "Retired", "e_retired", is_active=False),
            # `single` now, but `e_email` is on disk from when it was `multi`.
            _row("acme", "Email", "e_email", cardinality="single"),
        ])

        surface = (await resolve_query_surface(session, [SCHEMA]))[SCHEMA]

        assert surface.table_names == {SUBJECT_TABLE_NAME, "e_skill"}
        assert "e_retired" not in surface.child_tables
        assert "e_email" not in surface.child_tables
        assert [c.name for c in surface.subject_columns] == ["email"]

    async def test_schemas_stay_isolated_and_every_requested_schema_is_present(self):
        """Row 70 — one tenant's `e_skill` says nothing about another's surface."""
        other = "tenant_globex"
        session = _SurfaceSession([
            _row("acme", "Skill", "e_skill"),
            _row("globex", "Contract", "e_contract"),
            _row("unrequested", "Ghost", "e_ghost"),
        ])

        resolved = await resolve_query_surface(session, [SCHEMA, other, "tenant_empty"])

        assert resolved[SCHEMA].table_names == {SUBJECT_TABLE_NAME, "e_skill"}
        assert resolved[other].table_names == {SUBJECT_TABLE_NAME, "e_contract"}
        # A tenant with no definitions still has `subject` — the reconciler creates it.
        assert resolved["tenant_empty"].table_names == {SUBJECT_TABLE_NAME}
        assert "e_ghost" not in {t for s in resolved.values() for t in s.table_names}

    async def test_base_label_definition_resolves_under_its_own_name(self):
        """Row 71 — ADR-008: a base-model tenant's labels are `PER`/`ORG`, and the association
        runs through `base_label_mapping`, never through equality against the name."""
        session = _SurfaceSession([
            _row("acme", "Person", "e_person", base_label_mapping={"PER": 1}),
        ])

        surface = (await resolve_query_surface(session, [SCHEMA]))[SCHEMA]

        assert surface.table_names == {SUBJECT_TABLE_NAME, "e_person"}
        definition = surface.child_tables["e_person"]
        assert definition.name == "Person"
        assert entity_type_literals(definition) == ["PER", "PERSON"]

    async def test_generated_tables_is_the_name_projection_of_the_surface(self):
        """Row 66 / task 1.5 — the wrapper is a pure narrowing, not a second resolver."""
        rows = [
            _row("acme", "Skill", "e_skill"),
            _row("acme", "Email", "e_email", cardinality="single"),
            _row("acme", "Retired", "e_retired", is_active=False),
        ]

        names = await resolve_generated_tables(_SurfaceSession(rows), [SCHEMA])
        surfaces = await resolve_query_surface(_SurfaceSession(rows), [SCHEMA])

        assert names == {SCHEMA: surfaces[SCHEMA].table_names}
        assert names[SCHEMA] == {SUBJECT_TABLE_NAME, "e_skill"}

    async def test_no_schemas_takes_no_query(self):
        session = _SurfaceSession([_row("acme", "Skill", "e_skill")])

        assert await resolve_query_surface(session, []) == {}
        assert session.statements == []

    async def test_surface_equals_what_the_reconciler_maintains(self):
        """The single-source rule, asserted across the resolver rather than the pure layer."""
        rows = [
            _row("acme", "Skill", "e_skill"),
            _row("acme", "Email", "e_email", cardinality="single"),
            _row("acme", "Retired", "e_retired", is_active=False),
        ]
        specs = [
            _spec("Skill", "e_skill"),
            _spec("Email", "e_email", cardinality="single"),
            _spec("Retired", "e_retired", is_active=False),
        ]

        surface = (await resolve_query_surface(_SurfaceSession(rows), [SCHEMA]))[SCHEMA]

        assert surface.table_names == expected_table_names(specs)

    async def test_a_definition_added_later_appears_at_the_next_resolution(self):
        """Row 7 — the surface is read from the catalog per question, so a new definition
        reaches the prompt, the whitelist, and the grants without a deployment."""
        session = _SurfaceSession([_row("acme", "Skill", "e_skill")])

        before = (await resolve_query_surface(session, [SCHEMA]))[SCHEMA]
        assert before.table_names == {SUBJECT_TABLE_NAME, "e_skill"}

        session.rows.append(_row("acme", "Certification", "e_certification"))
        after = (await resolve_query_surface(session, [SCHEMA]))[SCHEMA]

        assert after.table_names == {SUBJECT_TABLE_NAME, "e_skill", "e_certification"}
        assert "e_certification" in after.child_tables


class TestSubjectColumnTypeConvergence:
    """`ADD COLUMN IF NOT EXISTS` does nothing to a column that already exists, so a
    `value_kind` edit moved the catalog and left the column behind — while the projection and
    the query surface both went on trusting the catalog. verification.md rows 1-6, 9.
    """

    DEFINITIONS = [
        _spec("PHONE_NUMBER", "e_phone_number", cardinality="single", value_kind="number"),
        _spec("NAME", "e_name", cardinality="single"),
        _spec("START_DATE", "e_start_date", cardinality="single", value_kind="date"),
        _spec("SKILL", "e_skill"),
    ]

    def test_a_diverging_column_is_retyped(self):
        """Row 1 — the `PHONE_NUMBER` shape: catalog says number, disk says text."""
        statements = build_subject_column_type_statements(
            SCHEMA, self.DEFINITIONS, {"phone_number": "text", "name": "text", "start_date": "date"}
        )

        assert statements == [
            f"ALTER TABLE {SCHEMA}.{SUBJECT_TABLE_NAME} ALTER COLUMN phone_number "
            "TYPE DOUBLE PRECISION USING NULL::DOUBLE PRECISION"
        ]

    def test_every_direction_converges(self):
        """Rows 1-3 — including the pair PostgreSQL provides no cast between."""
        actual = {"phone_number": "date", "name": "double precision", "start_date": "text"}

        retyped = {
            column: (was, declared)
            for column, was, declared in diverging_subject_columns(self.DEFINITIONS, actual)
        }

        assert retyped == {
            "phone_number": ("date", "DOUBLE PRECISION"),
            "name": ("double precision", "TEXT"),
            "start_date": ("text", "DATE"),
        }

    def test_a_matching_column_is_left_alone(self):
        """Row 5 — and the reason Risk 1 exists: a spelling mismatch here would retype, and so
        blank, every column on every reconcile."""
        actual = {"phone_number": "double precision", "name": "text", "start_date": "date"}

        assert diverging_subject_columns(self.DEFINITIONS, actual) == []
        assert build_subject_column_type_statements(SCHEMA, self.DEFINITIONS, actual) == []

    def test_a_column_that_does_not_exist_yet_is_not_a_divergence(self):
        """Row 6 — `ADD COLUMN` in the same statement list creates it at the declared type."""
        assert build_subject_column_type_statements(SCHEMA, self.DEFINITIONS, {}) == []

    def test_an_off_surface_column_is_left_at_its_type(self):
        """Row 11 — a deactivated or `multi`-flipped definition's column is retained exactly as
        its child table is: nothing projects into it and nothing may query it, so retyping it
        would blank rows nobody asked about."""
        definitions = [
            _spec("EMAIL", "e_email", cardinality="single", value_kind="number", is_active=False),
            _spec("PHONE_NUMBER", "e_phone_number", value_kind="number"),  # multi now
        ]
        actual = {"email": "text", "phone_number": "text"}

        assert diverging_subject_columns(definitions, actual) == []

    def test_the_conversion_clears_rather_than_casts(self):
        """A cast that succeeds is still wrong: the column holds a projection computed under the
        old kind, and the correct value under the new one is a different projection of the same
        entity. `document_entities` keeps every value; the projection re-derives the column."""
        statements = build_subject_column_type_statements(
            SCHEMA, self.DEFINITIONS, {"phone_number": "text"}
        )

        assert "USING NULL::DOUBLE PRECISION" in statements[0]
        assert "::text" not in statements[0]

    def test_retyping_emits_nothing_destructive(self):
        """Row 9 — asserted over the whole script, as the rest of this module's DDL is."""
        actual = {"phone_number": "text", "name": "date", "start_date": "double precision"}
        script = "\n".join(
            build_entity_table_statements(SCHEMA, self.DEFINITIONS)
            + build_subject_column_type_statements(SCHEMA, self.DEFINITIONS, actual)
        ).upper()

        for keyword in DESTRUCTIVE_KEYWORDS:
            assert keyword not in script

    def test_the_information_schema_spelling_map_is_total(self):
        """Risk 1 — every type `subject_column_type` can return needs a spelling, or that type's
        columns compare unequal forever."""
        from src.shared.entity_views import (
            _COLUMN_TYPE_BY_TYPED_FIELD,
            _INFORMATION_SCHEMA_TYPE,
            SUBJECT_TEXT_COLUMN_TYPE,
        )

        emitted = set(_COLUMN_TYPE_BY_TYPED_FIELD.values()) | {SUBJECT_TEXT_COLUMN_TYPE}

        assert emitted <= set(_INFORMATION_SCHEMA_TYPE)
        # And the spellings are what the server actually reports, lower-cased and unqualified.
        for spelling in _INFORMATION_SCHEMA_TYPE.values():
            assert spelling == spelling.lower()

    def test_every_supported_value_kind_has_a_declared_type(self):
        """`duration`, `money`, and `boolean` are unchanged by this work — they keep declaring
        DOUBLE PRECISION, exactly as before."""
        from src.extraction_service.services.semantic_normalizer import SUPPORTED_KINDS
        from src.shared.entity_views import subject_column_type

        declared = {kind: subject_column_type(kind) for kind in SUPPORTED_KINDS}

        assert declared == {
            "text": "TEXT",
            "number": "DOUBLE PRECISION",
            "money": "DOUBLE PRECISION",
            "duration": "DOUBLE PRECISION",
            "boolean": "DOUBLE PRECISION",
            "date": "DATE",
        }

    def test_a_kind_change_within_one_type_needs_no_ddl(self):
        """`number -> money -> duration` all declare DOUBLE PRECISION, so the column is already
        right and nothing is emitted — the change of representation is the projection's job."""
        definitions = [_spec("YOE", "e_yoe", cardinality="single", value_kind="duration")]

        assert build_subject_column_type_statements(
            SCHEMA, definitions, {"yoe": "double precision"}
        ) == []
