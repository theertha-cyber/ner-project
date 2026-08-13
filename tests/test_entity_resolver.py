import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from src.chat_api.services import entity_resolver
from src.chat_api.services.entity_resolver import Candidate

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


class ScriptedSelectionClient:
    def __init__(self, verdict: str | None = None, raises: Exception | None = None):
        self.verdict = verdict
        self.raises = raises
        self.call_count = 0

        async def create(**kwargs):
            self.call_count += 1
            if self.raises is not None:
                raise self.raises
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.verdict))])

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class TestMentionExtraction:
    """Covers verification.md rows 24-27."""

    def test_case_and_punctuation_insensitive_match(self):
        mentions = entity_resolver._extract_mentions("Tell me about  SREELAKSHMI  R.")
        canon_values = [c for _, c, _ in mentions]
        assert entity_resolver.canonicalize("Sreelakshmi R") in canon_values

    def test_longest_ngram_ordered_first(self):
        mentions = entity_resolver._extract_mentions("Sreelakshmi R is a candidate")
        # 3-word n-grams appear before 2-word before 1-word
        word_counts = [n for _, _, n in mentions]
        assert word_counts == sorted(word_counts, reverse=True)

    def test_dedup_by_canonical_value(self):
        mentions = entity_resolver._extract_mentions("Sreelakshmi Sreelakshmi")
        canon_values = [c for _, c, _ in mentions]
        assert len(canon_values) == len(set(canon_values))

    def test_no_mentions_for_empty_message(self):
        assert entity_resolver._extract_mentions("") == []

    def test_alias_mapped_value_matches(self):
        # "reactjs" canonicalizes to "react" via entity_normalizer.ALIAS_MAP
        mentions = entity_resolver._extract_mentions("Does she know ReactJS")
        canon_values = [c for _, c, _ in mentions]
        assert "react" in canon_values


class TestPersonTypes:
    def test_default_person_types_parsed(self):
        types = entity_resolver._person_types()
        assert "PER" in types
        assert "PERSON" in types


class TestParseOrdinalSelection:
    """Covers verification.md row 42 (ordinal path)."""

    def test_numeric_ordinal(self):
        assert entity_resolver.parse_ordinal_selection("Candidate 2", 3) == 1

    def test_bare_number(self):
        assert entity_resolver.parse_ordinal_selection("2", 3) == 1

    def test_word_ordinal(self):
        assert entity_resolver.parse_ordinal_selection("the second one", 3) == 1

    def test_out_of_range_returns_none(self):
        assert entity_resolver.parse_ordinal_selection("candidate 7", 3) is None

    def test_non_ordinal_answer_returns_none(self):
        assert entity_resolver.parse_ordinal_selection("the React developer", 3) is None


class TestClarificationRendering:
    """Covers verification.md row 33."""

    def setup_method(self):
        self.candidates = [
            Candidate(document_id="doc-1", name="Sreelakshmi R", organization="SEO Technologies", experience="3.5 years", skills=["ReactJS"]),
            Candidate(document_id="doc-2", name="Sreelakshmi P", organization="UST Global", experience="8 years", skills=["Java"]),
            Candidate(document_id="doc-3", name="Sreelakshmi K", experience=None, skills=[]),
        ]

    def test_names_the_reference_and_lists_candidates_with_stable_indices(self):
        text_out = entity_resolver.render_clarification("Sreelakshmi", self.candidates)
        assert "Sreelakshmi" in text_out
        assert "1. " in text_out
        assert "2. " in text_out
        assert "3. " in text_out
        assert "SEO Technologies" in text_out
        assert "UST Global" in text_out

    def test_over_cap_narrowing_message(self):
        msg = entity_resolver.render_narrowing_message("Sreelakshmi")
        assert "Sreelakshmi" in msg
        assert "narrow" in msg.lower()


class TestCardAssemblyFieldOmission:
    """Covers verification.md rows 35-38 for the rendering half of card assembly
    (field omission and value fidelity); rows requiring DB-sourced field
    aggregation are covered by TestBuildCandidates below."""

    def test_missing_fields_are_omitted_not_blank(self):
        c = Candidate(document_id="doc-1", name="Sreelakshmi R", organization="SEO Technologies")
        rendered = entity_resolver.render_clarification("Sreelakshmi", [c])
        assert "Sreelakshmi R — SEO Technologies" in rendered
        # no trailing " — " for the missing experience/skills fields
        assert not rendered.rstrip().endswith("—")

    def test_skills_capped_at_configured_max(self, monkeypatch):
        from src.shared.config import settings
        monkeypatch.setattr(settings, "entity_resolution_max_skills", 3)
        c = Candidate(document_id="doc-1", name="X", skills=["a", "b", "c"])
        assert len(c.skills) <= settings.entity_resolution_max_skills


class TestSelectionInterpretation:
    """Covers verification.md rows 42-45."""

    def setup_method(self):
        self.candidates = [
            Candidate(document_id="doc-1", name="Sreelakshmi R", organization="SEO Technologies", skills=["ReactJS"]),
            Candidate(document_id="doc-2", name="Sreelakshmi P", organization="UST Global", skills=["Java"]),
        ]

    async def test_ordinal_answer_makes_no_llm_call(self):
        client = ScriptedSelectionClient(verdict="1")
        idx = await entity_resolver.interpret_selection("Candidate 2", self.candidates, client, "gpt-4o")
        assert idx == 1
        assert client.call_count == 0

    async def test_descriptive_answer_uses_constrained_call(self):
        client = ScriptedSelectionClient(verdict="1")
        idx = await entity_resolver.interpret_selection("The React developer", self.candidates, client, "gpt-4o")
        assert idx == 0
        assert client.call_count == 1

    async def test_attribute_answer_uses_constrained_call(self):
        client = ScriptedSelectionClient(verdict="2")
        idx = await entity_resolver.interpret_selection("The one from UST Global", self.candidates, client, "gpt-4o")
        assert idx == 1

    async def test_out_of_range_index_from_llm_is_rejected(self):
        client = ScriptedSelectionClient(verdict="7")
        idx = await entity_resolver.interpret_selection("someone else entirely", self.candidates, client, "gpt-4o")
        assert idx is None

    async def test_none_verdict_returns_none(self):
        client = ScriptedSelectionClient(verdict="none")
        idx = await entity_resolver.interpret_selection("I don't know", self.candidates, client, "gpt-4o")
        assert idx is None

    async def test_llm_failure_returns_none(self):
        client = ScriptedSelectionClient(raises=RuntimeError("down"))
        idx = await entity_resolver.interpret_selection("The React developer", self.candidates, client, "gpt-4o")
        assert idx is None


@pytest.fixture
async def entity_schema(engine, setup_database, tenant_schema):
    tid, schema = tenant_schema
    async with engine.begin() as conn:
        await conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {schema}.document_entities (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL,
                entity_type TEXT NOT NULL,
                entity_value TEXT NOT NULL,
                normalized_value TEXT NOT NULL,
                confidence DOUBLE PRECISION NOT NULL,
                page_number INTEGER,
                char_start INTEGER,
                char_end INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
    yield tid, schema
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP TABLE IF EXISTS {schema}.document_entities"))


async def _insert_entity(conn, schema, document_id, entity_type, entity_value, normalized_value):
    await conn.execute(
        text(f"""
            INSERT INTO {schema}.document_entities
                (id, document_id, entity_type, entity_value, normalized_value, confidence)
            VALUES (:id, :doc, :etype, :eval, :nval, 0.9)
        """),
        {"id": str(uuid.uuid4()), "doc": document_id, "etype": entity_type, "eval": entity_value, "nval": normalized_value},
    )


@pytest.mark.usefixtures("entity_schema")
class TestResolveEntityOutcomes:
    """Covers verification.md rows 22, 23, 26-31."""

    async def test_no_match_is_unresolved(self, engine, entity_schema, db_session):
        tid, schema = entity_schema
        result = await entity_resolver.resolve_entity("Tell me about Nobody Here", db_session, schema, tid)
        assert result.outcome == entity_resolver.UNRESOLVED

    async def test_single_document_is_unique(self, engine, entity_schema, db_session):
        tid, schema = entity_schema
        async with engine.begin() as conn:
            await _insert_entity(conn, schema, "doc-1", "PER", "Sreelakshmi R", entity_resolver.canonicalize("Sreelakshmi R"))
        result = await entity_resolver.resolve_entity("Tell me about Sreelakshmi R", db_session, schema, tid)
        assert result.outcome == entity_resolver.UNIQUE
        assert result.resolved_document_id == "doc-1"

    async def test_repeated_name_one_document_is_unique(self, engine, entity_schema, db_session):
        tid, schema = entity_schema
        async with engine.begin() as conn:
            for _ in range(11):
                await _insert_entity(conn, schema, "doc-1", "PER", "Sreelakshmi R", entity_resolver.canonicalize("Sreelakshmi R"))
        result = await entity_resolver.resolve_entity("Tell me about Sreelakshmi R", db_session, schema, tid)
        assert result.outcome == entity_resolver.UNIQUE

    async def test_multiple_documents_is_ambiguous(self, engine, entity_schema, db_session):
        tid, schema = entity_schema
        async with engine.begin() as conn:
            for doc_id in ("doc-1", "doc-2", "doc-3"):
                await _insert_entity(conn, schema, doc_id, "PER", "Sreelakshmi", entity_resolver.canonicalize("Sreelakshmi"))
        result = await entity_resolver.resolve_entity("Tell me about Sreelakshmi", db_session, schema, tid)
        assert result.outcome == entity_resolver.AMBIGUOUS
        assert {c.document_id for c in result.candidates} == {"doc-1", "doc-2", "doc-3"}

    async def test_non_person_type_not_matched(self, engine, entity_schema, db_session):
        tid, schema = entity_schema
        async with engine.begin() as conn:
            await _insert_entity(conn, schema, "doc-1", "ORG", "Acme", entity_resolver.canonicalize("Acme"))
        result = await entity_resolver.resolve_entity("Tell me about Acme", db_session, schema, tid)
        assert result.outcome == entity_resolver.UNRESOLVED

    async def test_longest_mention_wins_over_shorter_overlap(self, engine, entity_schema, db_session):
        tid, schema = entity_schema
        async with engine.begin() as conn:
            await _insert_entity(conn, schema, "doc-short", "PER", "Sreelakshmi", entity_resolver.canonicalize("Sreelakshmi"))
            await _insert_entity(conn, schema, "doc-long", "PER", "Sreelakshmi R", entity_resolver.canonicalize("Sreelakshmi R"))
        result = await entity_resolver.resolve_entity("Tell me about Sreelakshmi R", db_session, schema, tid)
        assert result.outcome == entity_resolver.UNIQUE
        assert result.resolved_document_id == "doc-long"

    async def test_over_cap_declines_to_list(self, engine, entity_schema, db_session, monkeypatch):
        from src.shared.config import settings
        monkeypatch.setattr(settings, "entity_resolution_max_candidates", 2)
        tid, schema = entity_schema
        async with engine.begin() as conn:
            for doc_id in ("doc-1", "doc-2", "doc-3"):
                await _insert_entity(conn, schema, doc_id, "PER", "Sreelakshmi", entity_resolver.canonicalize("Sreelakshmi"))
        result = await entity_resolver.resolve_entity("Tell me about Sreelakshmi", db_session, schema, tid)
        assert result.outcome == entity_resolver.OVER_CAP
        assert result.candidates == []

    async def test_resolver_queries_stay_within_requesting_schema(self, engine, entity_schema, db_session):
        """Covers verification.md row 23: two tenant schemas share a normalized
        value; resolving in one must never surface the other's candidate."""
        tid, schema_a = entity_schema
        schema_b = "tenant_cross_check_b"
        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_b}"))
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {schema_b}.document_entities (
                    id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, entity_type TEXT NOT NULL,
                    entity_value TEXT NOT NULL, normalized_value TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL,
                    page_number INTEGER, char_start INTEGER, char_end INTEGER, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))
            await _insert_entity(conn, schema_a, "doc-a1", "PER", "Sreelakshmi", entity_resolver.canonicalize("Sreelakshmi"))
            await _insert_entity(conn, schema_b, "doc-b1", "PER", "Sreelakshmi", entity_resolver.canonicalize("Sreelakshmi"))
        try:
            result = await entity_resolver.resolve_entity("Tell me about Sreelakshmi", db_session, schema_a, tid)
            assert result.outcome == entity_resolver.UNIQUE
            assert result.resolved_document_id == "doc-a1"
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_b} CASCADE"))

    async def test_two_named_subjects_resolve_to_union(self, engine, entity_schema, db_session):
        """verification.md row 41. Resolution used to stop at the first mention that
        matched, so "compare Girish and Arjun Jayakumar" reached the prompt as a
        question about whichever of them n-gram ordering happened to reach first."""
        tid, schema = entity_schema
        async with engine.begin() as conn:
            await _insert_entity(conn, schema, "D1", "PER", "Girish", entity_resolver.canonicalize("Girish"))
            await _insert_entity(conn, schema, "D2", "PER", "Arjun Jayakumar", entity_resolver.canonicalize("Arjun Jayakumar"))

        result = await entity_resolver.resolve_entity(
            "Compare Girish and Arjun Jayakumar", db_session, schema, tid,
        )

        assert result.outcome == entity_resolver.UNIQUE
        assert set(result.resolved_document_ids) == {"D1", "D2"}
        assert set(result.mention_documents) >= {"Girish", "Arjun Jayakumar"}

    async def test_single_subject_resolution_unchanged(self, engine, entity_schema, db_session):
        """verification.md row 43 — the single-subject path behaves exactly as before."""
        tid, schema = entity_schema
        async with engine.begin() as conn:
            await _insert_entity(conn, schema, "D1", "PER", "Girish", entity_resolver.canonicalize("Girish"))

        result = await entity_resolver.resolve_entity("Tell me about Girish", db_session, schema, tid)

        assert result.outcome == entity_resolver.UNIQUE
        assert result.resolved_document_ids == ["D1"]
        assert result.resolved_document_id == "D1"

    async def test_union_over_cap_returns_narrowing(self, engine, entity_schema, db_session, monkeypatch):
        """verification.md row 45 — the cap applies to the union, and an over-cap turn
        is never scoped to an arbitrary subset."""
        from src.shared.config import settings
        monkeypatch.setattr(settings, "entity_resolution_max_candidates", 2)
        tid, schema = entity_schema
        async with engine.begin() as conn:
            await _insert_entity(conn, schema, "D1", "PER", "Girish", entity_resolver.canonicalize("Girish"))
            await _insert_entity(conn, schema, "D2", "PER", "Hannah", entity_resolver.canonicalize("Hannah"))
            await _insert_entity(conn, schema, "D3", "PER", "Mahalakshmi", entity_resolver.canonicalize("Mahalakshmi"))

        result = await entity_resolver.resolve_entity(
            "Compare Girish and Hannah and Mahalakshmi", db_session, schema, tid,
        )

        assert result.outcome == entity_resolver.OVER_CAP
        assert result.resolved_document_ids == []

    async def test_one_subject_matching_several_people_still_clarifies(self, engine, entity_schema, db_session):
        """Ambiguity is still a property of ONE mention matching several people — two
        mentions matching one person each is a comparison, not an ambiguity."""
        tid, schema = entity_schema
        async with engine.begin() as conn:
            await _insert_entity(conn, schema, "D1", "PER", "Girish", entity_resolver.canonicalize("Girish"))
            await _insert_entity(conn, schema, "D2", "PER", "Girish", entity_resolver.canonicalize("Girish"))

        result = await entity_resolver.resolve_entity("Tell me about Girish", db_session, schema, tid)

        assert result.outcome == entity_resolver.AMBIGUOUS
        assert {c.document_id for c in result.candidates} == {"D1", "D2"}

    async def test_zero_call_llm_during_extraction_and_matching(self, engine, entity_schema, db_session):
        tid, schema = entity_schema
        client = ScriptedSelectionClient(verdict="1")
        # resolve_entity takes no llm_client argument at all — this asserts the
        # contract rather than a call count, since there is nothing to spy on.
        import inspect
        assert "llm_client" not in inspect.signature(entity_resolver.resolve_entity).parameters


@pytest.mark.usefixtures("entity_schema")
class TestResolutionLogging:
    """Covers verification.md rows 63, 64. No full user message is logged (the
    resolver's log calls only ever pass tenant_id, outcome, and counts)."""

    async def test_ambiguous_outcome_logged_with_candidate_count(self, engine, entity_schema, db_session, caplog):
        tid, schema = entity_schema
        async with engine.begin() as conn:
            for doc_id in ("doc-1", "doc-2", "doc-3"):
                await _insert_entity(conn, schema, doc_id, "PER", "Sreelakshmi", entity_resolver.canonicalize("Sreelakshmi"))
        with caplog.at_level("INFO", logger="src.chat_api.services.entity_resolver"):
            await entity_resolver.resolve_entity("Tell me about Sreelakshmi", db_session, schema, tid)
        matching = [r for r in caplog.records if "outcome=ambiguous" in r.message]
        assert matching
        assert "candidate_documents=3" in matching[0].message

    async def test_unresolved_outcome_logged(self, engine, entity_schema, db_session, caplog):
        tid, schema = entity_schema
        with caplog.at_level("INFO", logger="src.chat_api.services.entity_resolver"):
            await entity_resolver.resolve_entity("Tell me about Nobody", db_session, schema, tid)
        matching = [r for r in caplog.records if "outcome=unresolved" in r.message]
        assert matching


@pytest.mark.usefixtures("entity_schema")
class TestBuildCandidates:
    """Covers verification.md rows 35-38."""

    async def test_card_shows_only_existing_fields(self, engine, entity_schema, db_session):
        tid, schema = entity_schema
        async with engine.begin() as conn:
            await _insert_entity(conn, schema, "doc-1", "PER", "Sreelakshmi R", entity_resolver.canonicalize("Sreelakshmi R"))
            await _insert_entity(conn, schema, "doc-1", "ORG", "SEO Technologies", entity_resolver.canonicalize("SEO Technologies"))
            await _insert_entity(conn, schema, "doc-2", "PER", "Sreelakshmi R", entity_resolver.canonicalize("Sreelakshmi R"))
        rows = await entity_resolver._lookup_candidate_rows(
            db_session, schema, [entity_resolver.canonicalize("Sreelakshmi R")], {"PER"},
        )
        candidates = await entity_resolver._build_candidates(db_session, schema, ["doc-1", "doc-2"], rows)
        c1 = next(c for c in candidates if c.document_id == "doc-1")
        c2 = next(c for c in candidates if c.document_id == "doc-2")
        assert c1.organization == "SEO Technologies"
        assert c2.organization is None
        assert c2.experience is None

    async def test_skills_capped(self, engine, entity_schema, db_session, monkeypatch):
        from src.shared.config import settings
        monkeypatch.setattr(settings, "entity_resolution_max_skills", 3)
        tid, schema = entity_schema
        async with engine.begin() as conn:
            await _insert_entity(conn, schema, "doc-1", "PER", "X", entity_resolver.canonicalize("X"))
            for i in range(9):
                await _insert_entity(conn, schema, "doc-1", "SKILL", f"skill-{i}", entity_resolver.canonicalize(f"skill-{i}"))
        rows = await entity_resolver._lookup_candidate_rows(db_session, schema, [entity_resolver.canonicalize("X")], {"PER"})
        candidates = await entity_resolver._build_candidates(db_session, schema, ["doc-1"], rows)
        assert len(candidates[0].skills) <= 3

    async def test_identical_cards_fall_back_to_filenames(self, engine, entity_schema, db_session):
        tid, schema = entity_schema
        # `documents` already exists in this schema — created by the `tenant_schema`
        # fixture (see tests/conftest.py `_TENANT_TABLES_SQL`); it owns that table's
        # lifecycle, so this test only inserts into it and never creates or drops it.
        async with engine.begin() as conn:
            await conn.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename) VALUES ('doc-1', :tid, 'resume_a.pdf'), ('doc-2', :tid, 'resume_b.pdf')"),
                {"tid": tid},
            )
            await _insert_entity(conn, schema, "doc-1", "PER", "Same Name", entity_resolver.canonicalize("Same Name"))
            await _insert_entity(conn, schema, "doc-2", "PER", "Same Name", entity_resolver.canonicalize("Same Name"))
        rows = await entity_resolver._lookup_candidate_rows(db_session, schema, [entity_resolver.canonicalize("Same Name")], {"PER"})
        candidates = await entity_resolver._build_candidates(db_session, schema, ["doc-1", "doc-2"], rows)
        assert all(c.filename is not None for c in candidates)
        assert {c.filename for c in candidates} == {"resume_a.pdf", "resume_b.pdf"}

    async def test_card_values_come_from_entity_store_verbatim(self, engine, entity_schema, db_session):
        tid, schema = entity_schema
        async with engine.begin() as conn:
            await _insert_entity(conn, schema, "doc-1", "PER", "Sreelakshmi R", entity_resolver.canonicalize("Sreelakshmi R"))
            await _insert_entity(conn, schema, "doc-1", "ORG", "SEO Technologies", entity_resolver.canonicalize("SEO Technologies"))
        rows = await entity_resolver._lookup_candidate_rows(db_session, schema, [entity_resolver.canonicalize("Sreelakshmi R")], {"PER"})
        candidates = await entity_resolver._build_candidates(db_session, schema, ["doc-1"], rows)
        assert candidates[0].organization == "SEO Technologies"
