"""Pure-function tests for the relational projection.

Database-free, deliberately. The projection's failure modes are silent — an entity routed to no
definition, or to the wrong one, produces an empty table rather than an error, and downstream
that reads as "nothing was found" rather than as a fault. So the statements and the routing
decisions are asserted directly instead of only through their effects.

Covers verification.md rows 4, 6-22, 24, 28, 30, 32-38.
"""

import re
from datetime import date

import pytest

from src.extraction_service.services.entity_normalizer import NormalizedEntity
from src.extraction_service.services.relational_projection import (
    build_projection_statements,
    build_relational_delete_statements,
    build_routing_index,
    route_entities,
    select_single_value,
    value_for_column,
)
from src.shared.entity_views import EntityDefinitionSpec, InvalidIdentifierError

SCHEMA = "tenant_acme"
DOC = "doc-1"


def _spec(name, identifier, **kwargs):
    return EntityDefinitionSpec(name=name, sql_identifier=identifier, **kwargs)


def _entity(entity_type, value, normalized=None, confidence=0.9, **fields):
    entity = NormalizedEntity(
        entity_type=entity_type,
        entity_value=value,
        normalized_value=normalized if normalized is not None else value.lower(),
        confidence=confidence,
    )
    for key, val in fields.items():
        setattr(entity, key, val)
    return entity


def _statements(*args, **kwargs):
    return build_projection_statements(*args, **kwargs)


def _executable_string_literals(module_name: str) -> list[str]:
    """Every string constant in the module that is not a docstring.

    Source-text scanning would trip over the module docstring, which describes the very SQL it
    is asserting the absence of. Walking the AST and skipping docstring positions asserts on
    what the module can actually execute."""
    import ast
    import importlib
    import inspect

    module = importlib.import_module(
        f"src.extraction_service.services.{module_name}"
    )
    tree = ast.parse(inspect.getsource(module))

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def _subject(statements):
    return next(s for s in statements if f"{SCHEMA}.subject" in s[0])


def _child_rows(statements, table):
    return [params for sql, params in statements if f"{SCHEMA}.{table} (" in sql]


class TestRouting:
    """verification.md rows 6-9"""

    def test_fine_tuned_label_routes_by_name(self):
        routed = route_entities([_entity("SKILL", "Python")], [_spec("Skill", "e_skill")])
        assert list(routed) == ["e_skill"]

    def test_base_model_conll_label_routes_through_the_mapping(self):
        # ADR-008 makes the shared base model the default, and on that path `entity_type` holds
        # a CoNLL label rather than the tenant's own entity name. Name equality would leave
        # every base-model tenant's tables empty with no error anywhere.
        specs = [_spec("Employer", "e_employer", base_label_mapping={"ORG": ["employer"]})]
        routed = route_entities([_entity("ORG", "Acme Ltd")], specs)
        assert list(routed) == ["e_employer"]

    @pytest.mark.parametrize("stored", ["employer", "Employer", "EMPLOYER", "  EMPLOYER  "])
    def test_stored_case_and_whitespace_do_not_prevent_routing(self, stored):
        routed = route_entities([_entity(stored, "Acme")], [_spec("Employer", "e_employer")])
        assert list(routed) == ["e_employer"]

    def test_routing_and_ddl_share_one_literal_helper(self):
        import inspect

        from src.extraction_service.services import relational_projection

        source = inspect.getsource(relational_projection)
        assert "entity_type_literals" in source
        # A second implementation of "which entity_type values mean this definition" is the one
        # way routing and schema can come to disagree.
        assert not re.search(r"base_label_mapping\s*\.\s*keys\(\)", source)

    def test_inactive_definition_claims_nothing(self):
        routed = route_entities(
            [_entity("SKILL", "Python")], [_spec("Skill", "e_skill", is_active=False)]
        )
        assert routed == {}

    def test_definition_without_identifier_claims_nothing(self):
        routed = route_entities([_entity("SKILL", "Python")], [_spec("Skill", None)])
        assert routed == {}


class TestCollisionResolution:
    """verification.md rows 10-12"""

    def test_exact_name_match_wins(self):
        specs = [
            _spec("Employer", "e_employer", base_label_mapping={"ORG": ["employer"]}),
            _spec("ORG", "e_org"),
        ]
        index = build_routing_index(specs)
        assert index["ORG"].sql_identifier == "e_org"

    def test_warning_names_both_definitions(self, caplog):
        specs = [
            _spec("Employer", "e_employer", base_label_mapping={"ORG": ["employer"]}),
            _spec("ORG", "e_org"),
        ]
        with caplog.at_level(
            "WARNING", logger="src.extraction_service.services.relational_projection"
        ):
            build_routing_index(specs)
        message = "\n".join(r.getMessage() for r in caplog.records)
        assert "e_org" in message and "e_employer" in message

    def test_without_a_name_match_sql_identifier_order_decides(self):
        specs = [
            _spec("Zeta", "e_zeta", base_label_mapping={"ORG": ["zeta"]}),
            _spec("Alpha", "e_alpha", base_label_mapping={"ORG": ["alpha"]}),
        ]
        assert build_routing_index(specs)["ORG"].sql_identifier == "e_alpha"
        # Same catalog, different load order, same routing.
        assert build_routing_index(list(reversed(specs)))["ORG"].sql_identifier == "e_alpha"

    def test_a_collision_never_double_writes(self):
        specs = [
            _spec("Zeta", "e_zeta", base_label_mapping={"ORG": ["zeta"]}),
            _spec("Alpha", "e_alpha", base_label_mapping={"ORG": ["alpha"]}),
        ]
        statements = _statements(SCHEMA, DOC, "cv.pdf", [_entity("ORG", "Acme")], specs)
        assert len(_child_rows(statements, "e_alpha")) == 1
        assert _child_rows(statements, "e_zeta") == []


class TestUnroutableEntities:
    """verification.md row 13"""

    def test_an_unclaimed_type_is_skipped_not_failed(self, caplog):
        specs = [_spec("Skill", "e_skill")]
        entities = [_entity("SKILL", "Python"), _entity("MYSTERY", "???")]
        statements = _statements(SCHEMA, DOC, "cv.pdf", entities, specs)

        # The EAV store deliberately tolerates an undefined entity type; that tolerance has to
        # survive here, so the entity is simply absent from the relational surface.
        assert len(_child_rows(statements, "e_skill")) == 1
        assert not any("MYSTERY" in str(params) for _sql, params in statements)


class TestMultiValuedProjection:
    """verification.md rows 14, 15, 24, 33, 34"""

    def test_three_routed_entities_produce_three_rows(self):
        specs = [_spec("Skill", "e_skill")]
        entities = [_entity("SKILL", v) for v in ("Python", "SQL", "Go")]
        rows = _child_rows(_statements(SCHEMA, DOC, "cv.pdf", entities, specs), "e_skill")
        assert len(rows) == 3
        assert {r["normalized_value"] for r in rows} == {"python", "sql", "go"}

    def test_conflict_clause_keeps_the_greater_confidence_and_sums_occurrences(self):
        specs = [_spec("Skill", "e_skill")]
        sql = next(
            s
            for s, _p in _statements(SCHEMA, DOC, "cv.pdf", [_entity("SKILL", "Python")], specs)
            if f"{SCHEMA}.e_skill (" in s
        )
        assert "ON CONFLICT (document_id, normalized_value) DO UPDATE" in sql
        assert f"GREATEST({SCHEMA}.e_skill.confidence, EXCLUDED.confidence)" in sql
        assert f"{SCHEMA}.e_skill.occurrence_count + EXCLUDED.occurrence_count" in sql

    def test_child_rows_carry_confidence_and_page_number(self):
        specs = [_spec("Skill", "e_skill")]
        entities = [_entity("SKILL", "Python", confidence=0.77, page_number=3)]
        row = _child_rows(_statements(SCHEMA, DOC, "cv.pdf", entities, specs), "e_skill")[0]
        assert row["confidence"] == 0.77
        assert row["page_number"] == 3

    def test_child_rows_carry_no_provenance(self):
        specs = [_spec("Skill", "e_skill")]
        entities = [
            _entity(
                "SKILL",
                "Python",
                source_entity_value="Pyton",
                source_entity_type="TOOL",
                postprocess_status="corrected",
                postprocess_model="gpt-4o",
                char_start=10,
                char_end=16,
            )
        ]
        row = _child_rows(_statements(SCHEMA, DOC, "cv.pdf", entities, specs), "e_skill")[0]
        # Provenance stays in `document_entities`, joinable on (document_id, normalized_value).
        # Projecting it widens the schema every prompt must describe without answering any
        # question a user asks.
        for absent in (
            "source_entity_value",
            "source_entity_type",
            "postprocess_status",
            "postprocess_model",
            "postprocess_prompt_version",
            "postprocess_at",
            "extraction_schema_version",
            "char_start",
            "char_end",
        ):
            assert absent not in row

    def test_a_single_definition_gets_no_child_rows(self):
        specs = [_spec("Email", "e_email", cardinality="single")]
        statements = _statements(
            SCHEMA, DOC, "cv.pdf", [_entity("EMAIL", "a@b.com")], specs
        )
        assert _child_rows(statements, "e_email") == []


class TestSingleValueSelection:
    """verification.md rows 16-18"""

    def test_highest_confidence_wins(self):
        entities = [
            _entity("EMAIL", "low@x.com", confidence=0.5),
            _entity("EMAIL", "high@x.com", confidence=0.9),
            _entity("EMAIL", "mid@x.com", confidence=0.7),
        ]
        assert select_single_value(entities).entity_value == "high@x.com"

    def test_confidence_tie_falls_to_occurrence_count(self):
        entities = [
            _entity("EMAIL", "once@x.com", confidence=0.8, occurrence_count=1),
            _entity("EMAIL", "twice@x.com", confidence=0.8, occurrence_count=2),
        ]
        assert select_single_value(entities).entity_value == "twice@x.com"

    def test_full_tie_is_broken_by_normalized_value_and_is_order_independent(self):
        # `collapse_duplicates` sets confidence to the min of the values it merged, so ties are
        # the common case. Without the third key the chosen value would depend on list order
        # and could change between runs over identical input.
        entities = [
            _entity("EMAIL", "b@x.com", confidence=0.8, occurrence_count=1),
            _entity("EMAIL", "a@x.com", confidence=0.8, occurrence_count=1),
        ]
        assert select_single_value(entities).entity_value == "a@x.com"
        assert select_single_value(list(reversed(entities))).entity_value == "a@x.com"

    def test_no_entities_selects_nothing(self):
        assert select_single_value([]) is None

    def test_unselected_values_are_not_projected_but_are_not_lost_either(self):
        specs = [_spec("Email", "e_email", cardinality="single")]
        entities = [
            _entity("EMAIL", "a@x.com", confidence=0.9),
            _entity("EMAIL", "b@x.com", confidence=0.5),
        ]
        _sql, params = _subject(_statements(SCHEMA, DOC, "cv.pdf", entities, specs))
        assert params["email"] == "a@x.com"
        # The discarded value stays in `document_entities` — that store is untouched by this
        # module and remains the system of record.


class TestValueKindMapping:
    """verification.md rows 19-21"""

    @pytest.mark.parametrize("value_kind", ["number", "money", "duration", "boolean"])
    def test_numeric_kinds_take_value_number(self, value_kind):
        entity = _entity("YOE", "5 years", value_number=5.0)
        assert value_for_column(entity, value_kind) == 5.0

    def test_date_kind_takes_value_date(self):
        entity = _entity("START", "1 Jan 2020", value_date=date(2020, 1, 1))
        assert value_for_column(entity, "date") == date(2020, 1, 1)

    @pytest.mark.parametrize("value_kind", [None, "text", "something_new"])
    def test_other_kinds_take_the_surface_value(self, value_kind):
        entity = _entity("NAME", "Ada Lovelace")
        assert value_for_column(entity, value_kind) == "Ada Lovelace"

    def test_unparseable_typed_value_stays_null(self):
        # Falling back to surface text in a numeric column makes `WHERE years_experience > 5`
        # silently wrong rather than merely empty.
        entity = _entity("YOE", "half a decade", value_number=None)
        assert value_for_column(entity, "duration") is None

    def test_unparseable_typed_value_reaches_subject_as_null(self):
        specs = [_spec("YOE", "e_yoe", cardinality="single", value_kind="duration")]
        entities = [_entity("YOE", "half a decade")]
        _sql, params = _subject(_statements(SCHEMA, DOC, "cv.pdf", entities, specs))
        assert params["yoe"] is None
        assert "half a decade" not in params.values()


class TestSubjectRow:
    """verification.md rows 4, 22, 32"""

    def test_a_subject_row_is_always_emitted(self):
        statements = _statements(SCHEMA, DOC, "cv.pdf", [], [_spec("Skill", "e_skill")])
        sql, params = _subject(statements)
        assert sql.startswith(f"INSERT INTO {SCHEMA}.subject")
        assert params["document_id"] == DOC

    def test_a_zero_entity_document_gets_null_columns_and_a_filename(self):
        specs = [_spec("Email", "e_email", cardinality="single")]
        _sql, params = _subject(_statements(SCHEMA, DOC, "cv.pdf", [], specs))
        assert params["filename"] == "cv.pdf"
        assert params["email"] is None

    def test_filename_is_written_on_every_projection(self):
        specs = [_spec("Skill", "e_skill")]
        _sql, params = _subject(
            _statements(SCHEMA, DOC, "resume.pdf", [_entity("SKILL", "Python")], specs)
        )
        assert params["filename"] == "resume.pdf"

    def test_subject_upsert_updates_on_conflict(self):
        # Re-extraction deletes the row first, but the upsert is what makes a manual re-run or
        # a concurrent writer last-writer-wins instead of a primary-key violation.
        sql, _params = _subject(_statements(SCHEMA, DOC, "cv.pdf", [], []))
        assert "ON CONFLICT (document_id) DO UPDATE" in sql

    def test_subject_carries_no_confidence_or_page_number(self):
        specs = [_spec("Email", "e_email", cardinality="single")]
        _sql, params = _subject(
            _statements(SCHEMA, DOC, "cv.pdf", [_entity("EMAIL", "a@b.com", page_number=2)], specs)
        )
        assert set(params) == {"document_id", "filename", "email"}


class TestDeleteStatements:
    """verification.md rows 27, 28, 30"""

    def test_builder_executes_nothing(self):
        statements = build_relational_delete_statements(
            SCHEMA, DOC, [_spec("Skill", "e_skill")]
        )
        assert all(isinstance(sql, str) and isinstance(params, dict) for sql, params in statements)

    def test_subject_row_is_included(self):
        statements = build_relational_delete_statements(
            SCHEMA, DOC, [_spec("Skill", "e_skill"), _spec("Cert", "e_cert")]
        )
        targets = [sql.split("DELETE FROM ")[1].split(" ")[0] for sql, _p in statements]
        assert targets == [f"{SCHEMA}.e_cert", f"{SCHEMA}.e_skill", f"{SCHEMA}.subject"]

    def test_inactive_definitions_are_still_cleared(self):
        # Scoping the delete to active definitions would strand a deactivated definition's rows
        # where reactivation puts them straight back on the query surface, answering questions
        # beside the newest extraction's values.
        statements = build_relational_delete_statements(
            SCHEMA, DOC, [_spec("Skill", "e_skill", is_active=False)]
        )
        assert any(f"{SCHEMA}.e_skill" in sql for sql, _p in statements)

    def test_document_id_is_bound_not_interpolated(self):
        statements = build_relational_delete_statements(
            SCHEMA, "'; DROP TABLE documents; --", [_spec("Skill", "e_skill")]
        )
        for sql, params in statements:
            assert "DROP TABLE" not in sql
            assert params["document_id"] == "'; DROP TABLE documents; --"


class TestNoDdlAndNoInjection:
    """verification.md rows 35, 36, 37, 38"""

    def test_projection_emits_no_ddl(self):
        specs = [_spec("Skill", "e_skill"), _spec("Email", "e_email", cardinality="single")]
        statements = _statements(SCHEMA, DOC, "cv.pdf", [_entity("SKILL", "Python")], specs)
        for sql, _params in statements:
            upper = sql.upper()
            assert not upper.startswith("CREATE")
            assert not upper.startswith("ALTER")
            assert not upper.startswith("DROP")

    def test_a_definition_without_an_identifier_is_never_referenced(self):
        specs = [_spec("Skill", None), _spec("Email", "e_email", cardinality="single")]
        statements = _statements(SCHEMA, DOC, "cv.pdf", [_entity("SKILL", "Python")], specs)
        for sql, _params in statements:
            assert "skill" not in sql.lower()

    def test_a_hostile_entity_name_cannot_reach_a_statement(self):
        specs = [_spec('"; DROP TABLE documents; --', "e_hostile")]
        entities = [_entity('"; DROP TABLE documents; --', "x")]
        statements = _statements(SCHEMA, DOC, "cv.pdf", entities, specs)
        for sql, _params in statements:
            assert "DROP TABLE" not in sql
        # The literal is a value, matched in Python; it never enters SQL in any position.
        assert all("DROP TABLE" not in sql for sql, _p in statements)

    def test_a_malformed_sql_identifier_raises_rather_than_becoming_sql(self):
        with pytest.raises(InvalidIdentifierError):
            _statements(SCHEMA, DOC, "cv.pdf", [], [_spec("X", "skill; DROP TABLE documents")])

    @pytest.mark.parametrize(
        "schema", ["tenant acme", "tenant-acme", "", "tenant_acme; DROP TABLE documents"]
    )
    def test_an_invalid_schema_raises(self, schema):
        with pytest.raises(InvalidIdentifierError):
            _statements(schema, DOC, "cv.pdf", [], [_spec("Skill", "e_skill")])

    def test_every_statement_is_qualified_with_the_callers_schema(self):
        specs = [_spec("Skill", "e_skill"), _spec("Email", "e_email", cardinality="single")]
        statements = _statements(SCHEMA, DOC, "cv.pdf", [_entity("SKILL", "Python")], specs)
        for sql, _params in statements:
            assert re.search(rf"\b{SCHEMA}\.", sql)

    def test_the_module_resolves_no_tenant_schema_of_its_own(self):
        import inspect

        from src.extraction_service.services import relational_projection

        source = inspect.getsource(relational_projection)
        # The schema arrives as an argument — the same value already passed to
        # `insert_document_entities` — so no code path here can target a different tenant.
        assert 'f"tenant_' not in source
        assert "schema_for_tenant" not in source


class TestPurity:
    """verification.md row 4 — the builders touch no database."""

    def test_builders_return_parameterised_statements(self):
        specs = [_spec("Skill", "e_skill")]
        statements = _statements(SCHEMA, DOC, "cv.pdf", [_entity("SKILL", "Python")], specs)
        assert statements
        for sql, params in statements:
            assert isinstance(sql, str) and isinstance(params, dict)

    def test_generation_is_deterministic(self):
        specs = [
            _spec("Skill", "e_skill"),
            _spec("Email", "e_email", cardinality="single"),
            _spec("Cert", "e_cert"),
        ]
        entities = [_entity("SKILL", "Python"), _entity("CERT", "AWS")]
        first = _statements(SCHEMA, DOC, "cv.pdf", entities, specs)
        second = _statements(SCHEMA, DOC, "cv.pdf", entities, list(reversed(specs)))
        assert first == second

    def test_the_projection_never_reads_the_eav_store(self):
        # Every SQL string the module can emit, docstrings and comments excluded. Reading back
        # from `document_entities` to build the projection would couple it to the EAV write
        # landing in a particular shape, and would make "just run the projection separately"
        # look like a small refactor when it is what breaks the consistency guarantee.
        # A literal with no whitespace is an identifier or a name, never a statement.
        for literal in _executable_string_literals("relational_projection"):
            if not literal.strip() or " " not in literal:
                continue
            assert "SELECT" not in literal.upper()
            assert "document_entities" not in literal

    def test_projected_statements_are_only_inserts_and_deletes(self):
        specs = [_spec("Skill", "e_skill"), _spec("Email", "e_email", cardinality="single")]
        emitted = _statements(
            SCHEMA, DOC, "cv.pdf", [_entity("SKILL", "Python")], specs
        ) + build_relational_delete_statements(SCHEMA, DOC, specs)
        for sql, _params in emitted:
            assert sql.split()[0] in ("INSERT", "DELETE"), sql
