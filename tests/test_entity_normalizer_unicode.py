"""Covers verification.md rows 8-11.

The defect: `canonicalize()` applied NFKC, casefold and `\\s+` collapse, none of which
touch U+200B (general category `Cf`, not `Zs`) or fold a curly apostrophe. On the
development tenant nine stored values carried a zero-width space and four a U+2019, so
`normalized_value = 'software engineer'` returned 2 rows where `ILIKE '%software
engineer%'` returned 7."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:54320/ner_test")

import uuid

import pytest
from sqlalchemy import text

from src.extraction_service.services.entity_normalizer import canonicalize, fold_text

ZWSP = "​"
BOM = "﻿"
RSQUO = "’"
EN_DASH = "–"
EM_DASH = "—"


class TestFormatCharactersAreRemoved:
    """Row 8."""

    def test_zero_width_space_prefix_is_stripped(self):
        assert canonicalize(f"{ZWSP}Software Engineer") == "software engineer"

    def test_zero_width_space_on_both_ends_is_stripped(self):
        # The exact stored form of the development tenant's COMPANY row.
        assert canonicalize(f"{ZWSP}Tenkasi{ZWSP}") == "tenkasi"

    def test_zero_width_space_inside_a_phrase_is_stripped(self):
        assert canonicalize(f"Sardar Raja College of Engineering, {ZWSP}Alangulam") == (
            "sardar raja college of engineering, alangulam"
        )

    def test_byte_order_mark_is_stripped(self):
        assert canonicalize(f"{BOM}B.E") == "b.e"

    def test_result_carries_no_format_characters(self):
        result = canonicalize(f"{ZWSP}M.E{BOM}")
        assert ZWSP not in result and BOM not in result


class TestTypographicPunctuationIsFolded:
    """Rows 9 and 10."""

    def test_right_single_quote_folds_to_ascii_apostrophe(self):
        result = canonicalize(f"St.Xavier{RSQUO}s College")
        assert RSQUO not in result
        assert result == "st.xavier's college"

    def test_left_single_quote_folds_to_ascii_apostrophe(self):
        assert canonicalize("‘Acme’") == "acme"

    def test_double_quotes_fold_to_ascii(self):
        assert canonicalize("“Quest Global”") == "quest global"

    def test_en_dash_folds_to_hyphen(self):
        assert canonicalize(f"Nanguneri {EN_DASH} 627108") == "nanguneri - 627108"

    def test_em_dash_folds_to_hyphen(self):
        assert canonicalize(f"Alpha{EM_DASH}Beta") == "alpha-beta"

    def test_a_lone_em_dash_canonicalizes_to_a_hyphen(self):
        """The development tenant stored a JOB_TITLE whose only content was an em dash;
        folding makes it an obvious artifact for the validity gate rather than an
        invisible one."""
        assert canonicalize(EM_DASH) == "-"


class TestExistingBehaviourIsPreserved:
    def test_alias_map_still_applies(self):
        assert canonicalize("ReactJS") == "react"
        assert canonicalize("Amazon Web Services") == "aws"

    def test_surrounding_punctuation_is_still_stripped(self):
        assert canonicalize("B.Sc.,") == "b.sc"
        assert canonicalize("Tamilnadu.") == "tamilnadu"

    def test_interior_punctuation_is_still_preserved(self):
        assert canonicalize("Uniqlo Co., Ltd.,") == "uniqlo co., ltd"

    def test_whitespace_is_still_collapsed(self):
        assert canonicalize("  Centizen   INC  ") == "centizen inc"


class TestCanonicalizeIsPure:
    """Row 11."""

    def test_repeated_calls_agree(self):
        value = f"{ZWSP}St.Xavier{RSQUO}s College,"
        assert canonicalize(value) == canonicalize(value)

    def test_canonicalize_is_idempotent(self):
        once = canonicalize(f"{ZWSP}Software Engineer,")
        assert canonicalize(once) == once

    def test_input_is_not_mutated(self):
        value = f"{ZWSP}Software Engineer"
        canonicalize(value)
        assert value == f"{ZWSP}Software Engineer"

    def test_no_network_database_or_model_call(self, monkeypatch):
        import socket

        def _forbidden(*args, **kwargs):
            raise AssertionError("canonicalize must not open a socket")

        monkeypatch.setattr(socket, "socket", _forbidden)
        monkeypatch.setattr(socket, "create_connection", _forbidden)
        assert canonicalize(f"{ZWSP}Software Engineer") == "software engineer"


class TestFoldTextHelper:
    def test_fold_text_leaves_ordinary_text_alone(self):
        assert fold_text("Centizen Inc.") == "Centizen Inc."

    def test_fold_text_preserves_case(self):
        """The evidence check in post-processing folds without casefolding, so the
        helper must not lowercase on its own."""
        assert fold_text(f"{ZWSP}Software Engineer") == "Software Engineer"


@pytest.mark.asyncio
class TestExactMatchSqlReachesTheRow:
    """Row 8's second clause: the point of folding is that the persisted row is
    reachable by the equality predicate a SQL generator writes."""

    async def test_persisted_value_matches_an_ascii_literal(self, engine, setup_database):
        tid = f"zwsp-{uuid.uuid4().hex[:6]}"
        schema = f"tenant_{tid.replace('-', '_')}"
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            await conn.execute(text(f"""
                CREATE TABLE {schema}.document_entities (
                    id VARCHAR PRIMARY KEY,
                    document_id VARCHAR NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_value TEXT NOT NULL,
                    normalized_value TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL
                )
            """))

        try:
            raw = f"{ZWSP}Software Engineer"
            async with engine.begin() as conn:
                await conn.execute(
                    text(f"""
                        INSERT INTO {schema}.document_entities
                            (id, document_id, entity_type, entity_value, normalized_value, confidence)
                        VALUES ('e1', 'doc-1', 'JOB_TITLE', :raw, :canon, 0.91)
                    """),
                    {"raw": raw, "canon": canonicalize(raw)},
                )
                matched = await conn.execute(
                    text(f"""
                        SELECT COUNT(*) FROM {schema}.document_entities
                        WHERE entity_type = 'JOB_TITLE' AND normalized_value = 'software engineer'
                    """)
                )
                assert matched.scalar() == 1
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
