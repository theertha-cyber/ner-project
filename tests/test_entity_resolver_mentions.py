"""Entity resolution never fired on real questions. Two causes, both here:

  1. Names are stored whole ("arjun jayakumar") but referred to in part ("arjun"),
     and the lookup tested only `normalized_value = ANY(:values)`.
  2. "arjuns resume" / "arjun's resume" canonicalise to "arjuns" / "arjun's", which
     equal no stored name at all.

Together they meant `resolve_entity("... arjuns resume")` returned UNRESOLVED, so the
retrieval plan was never scoped to that person's document.
"""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_OPENAI_API_KEY", "test-key")

import pytest

from src.chat_api.services import entity_resolver
from src.chat_api.services.entity_resolver import (
    UNIQUE,
    UNRESOLVED,
    _depossessive,
    _extract_mentions,
    _mention_matches,
)


class TestDepossessive:
    @pytest.mark.parametrize("given,expected", [
        ("arjun's", "arjun"),
        ("arjun’s", "arjun"),
        ("arjuns", "arjun"),
    ])
    def test_possessive_forms_reduce_to_the_name(self, given, expected):
        assert _depossessive(given) == expected

    def test_non_possessive_returns_none(self):
        assert _depossessive("arjun") is None

    def test_too_short_to_strip_returns_none(self):
        assert _depossessive("as") is None


class TestMentionMatches:
    def test_first_name_matches_a_full_stored_name(self):
        assert _mention_matches("arjun", "arjun jayakumar")

    def test_last_name_matches_a_full_stored_name(self):
        assert _mention_matches("jayakumar", "arjun jayakumar")

    def test_full_name_matches(self):
        assert _mention_matches("arjun jayakumar", "arjun jayakumar")

    def test_unrelated_name_does_not_match(self):
        assert not _mention_matches("hannah", "arjun jayakumar")

    def test_partial_word_does_not_match(self):
        """Substring matching would make "jay" resolve to "arjun jayakumar"."""
        assert not _mention_matches("jay", "arjun jayakumar")


class TestExtractMentionsStillCoversThePhrase:
    def test_possessive_token_is_produced_as_a_mention(self):
        canon = {c for _, c, _ in _extract_mentions("List the tools in arjuns resume")}
        assert "arjuns" in canon


class _FakeSession:
    """Stands in for the DB. `_lookup_candidate_rows` is patched out, so this only has
    to answer the tenant person-type query."""

    async def execute(self, statement, params=None):
        class _R:
            def fetchall(self):
                return []
        return _R()


@pytest.mark.asyncio
class TestResolveEntityEndToEnd:
    async def _resolve(self, monkeypatch, message, stored):
        rows = [
            {"document_id": d, "entity_type": "NAME", "entity_value": v, "normalized_value": v.lower()}
            for d, v in stored
        ]

        async def fake_lookup(session, schema, canonical_values, person_types):
            return [
                r for r in rows
                if any(_mention_matches(c, r["normalized_value"]) for c in canonical_values)
            ]

        monkeypatch.setattr(entity_resolver, "_lookup_candidate_rows", fake_lookup)
        monkeypatch.setattr(
            entity_resolver, "_resolve_tenant_person_types",
            lambda session, tenant_id: _coro({"NAME"}),
        )
        return await entity_resolver.resolve_entity(message, _FakeSession(), "tenant_x", "t1")

    async def test_bare_possessive_first_name_resolves_to_the_document(self, monkeypatch):
        """The exact failing question."""
        result = await self._resolve(
            monkeypatch,
            "List out all the tool framworks within arjuns resume",
            [("doc-1", "Arjun Jayakumar")],
        )
        assert result.outcome == UNIQUE
        assert result.resolved_document_id == "doc-1"
        assert result.resolved_entity_value == "Arjun Jayakumar"

    async def test_apostrophe_possessive_resolves(self, monkeypatch):
        result = await self._resolve(
            monkeypatch, "what tools are in arjun's resume", [("doc-1", "Arjun Jayakumar")],
        )
        assert result.outcome == UNIQUE
        assert result.resolved_document_id == "doc-1"

    async def test_plain_first_name_resolves(self, monkeypatch):
        result = await self._resolve(
            monkeypatch, "what tools does arjun know", [("doc-1", "Arjun Jayakumar")],
        )
        assert result.outcome == UNIQUE

    async def test_unknown_name_stays_unresolved(self, monkeypatch):
        result = await self._resolve(
            monkeypatch, "what tools does priya know", [("doc-1", "Arjun Jayakumar")],
        )
        assert result.outcome == UNRESOLVED

    async def test_real_name_ending_in_s_matches_before_possessive_stripping(self, monkeypatch):
        """"james" must resolve to James, not be shortened to "jame" and lost."""
        result = await self._resolve(
            monkeypatch, "what tools does james know", [("doc-1", "James Okafor")],
        )
        assert result.outcome == UNIQUE
        assert result.resolved_entity_value == "James Okafor"


def _coro(value):
    async def _inner(*args, **kwargs):
        return value
    return _inner()
