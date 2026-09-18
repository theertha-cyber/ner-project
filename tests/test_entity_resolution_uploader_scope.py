"""Verification for entity resolution — verification.md rows 59-61, plus the ADR-014 gap.

Two rules are enforced on the same two `document_entities` reads:

- Uploader visibility (rows 59-61). This path presents a candidate's *name* during
  disambiguation, before any retrieval result exists, so scoping retrieval alone would
  still have disclosed who appears in a colleague's resumes.
- Conversation visibility (ADR-014). This path reads `document_entities` directly —
  outside both the `Retriever` implementations and the generated-SQL scope rewrite — so
  it was never covered by ADR-014's channel enumeration, and a name extracted from a file
  attached in one conversation resolved from every other conversation of that tenant.
  The ADR states that guarantee as met, which is why the omission went unnoticed.
"""

import uuid

import pytest
from sqlalchemy import text

from src.chat_api.services import entity_resolver
from src.shared.document_visibility import ROLE_TENANT_ADMIN, RequestingUser

pytestmark = [pytest.mark.verification, pytest.mark.integration]

MINE = RequestingUser(user_id="recruiter-1", role="business_user")
THEIRS = RequestingUser(user_id="recruiter-2", role="business_user")
ADMIN = RequestingUser(user_id="boss", role=ROLE_TENANT_ADMIN)

CONV_A = "conv-a"
CONV_B = "conv-b"


@pytest.fixture
async def seeded_people(tenant_schema, engine):
    """Four documents, each holding one PERSON entity:

    - `own`      — uploaded by recruiter-1, library content
    - `other`    — uploaded by recruiter-2, library content
    - `system`   — ingested by a source system, library content
    - `attached` — uploaded by recruiter-1 into conversation A
    """
    tenant_id, schema = tenant_schema
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    people = {
        "own": ("recruiter-1", "human", None, "Arjun Own"),
        "other": ("recruiter-2", "human", None, "Arjun Other"),
        "system": (None, "source_system", None, "Arjun System"),
        "attached": ("recruiter-1", "human", CONV_A, "Arjun Attached"),
    }
    ids = {}

    async with session_factory() as session:
        await session.execute(
            text(f"ALTER TABLE {schema}.documents ADD COLUMN IF NOT EXISTS ingested_by_kind VARCHAR(32)")
        )
        await session.execute(
            text(f"ALTER TABLE {schema}.documents ADD COLUMN IF NOT EXISTS conversation_id VARCHAR")
        )
        await session.execute(
            text(f"""
                CREATE TABLE IF NOT EXISTS {schema}.document_entities (
                    id VARCHAR PRIMARY KEY,
                    document_id VARCHAR NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_value TEXT NOT NULL,
                    normalized_value TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL
                )
            """)
        )
        # `documents.conversation_id` carries a FK to `conversations` (ADR-011), so the
        # conversation has to exist before an attachment can point at it.
        await session.execute(
            text(
                f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) "
                "VALUES (:id, :tid, 'recruiter-1', 'A') ON CONFLICT (id) DO NOTHING"
            ),
            {"id": CONV_A, "tid": tenant_id},
        )
        for key, (uploader, kind, conv, name) in people.items():
            doc_id = f"doc-{key}-{uuid.uuid4()}"
            ids[key] = doc_id
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.documents
                        (id, tenant_id, filename, status, purpose, uploaded_by,
                         ingested_by_kind, conversation_id)
                    VALUES (:id, :tid, :fn, 'processed', 'query', :up, :kind, :conv)
                """),
                {"id": doc_id, "tid": tenant_id, "fn": f"{key}.pdf",
                 "up": uploader, "kind": kind, "conv": conv},
            )
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.document_entities
                        (id, document_id, entity_type, entity_value, normalized_value, confidence)
                    VALUES (:id, :doc, 'PER', :val, :norm, 0.95)
                """),
                {"id": str(uuid.uuid4()), "doc": doc_id, "val": name, "norm": name.lower()},
            )
        await session.commit()

    yield tenant_id, schema, ids, session_factory


async def _lookup(session_factory, schema, values, user, conversation_id=None):
    async with session_factory() as session:
        return await entity_resolver._lookup_candidate_rows(
            session, schema, values, {"PER"}, user, conversation_id
        )


# --- Rows 59-61: uploader visibility ------------------------------------------------


async def test_another_users_person_is_not_a_candidate(seeded_people):
    """Row 59 — the disclosure this change exists to stop, at the point where a *name*
    would have been shown."""
    _tid, schema, ids, factory = seeded_people
    rows = await _lookup(factory, schema, ["arjun other"], MINE)
    assert rows == []


async def test_the_users_own_person_still_resolves(seeded_people):
    """Row 61. The rule must not cost the user their own data."""
    _tid, schema, ids, factory = seeded_people
    rows = await _lookup(factory, schema, ["arjun own"], MINE)
    assert [r["document_id"] for r in rows] == [ids["own"]]


async def test_source_system_people_resolve_for_everyone(seeded_people):
    _tid, schema, ids, factory = seeded_people
    for user in (MINE, THEIRS):
        rows = await _lookup(factory, schema, ["arjun system"], user)
        assert [r["document_id"] for r in rows] == [ids["system"]]


async def test_a_shared_first_name_offers_only_visible_people(seeded_people):
    """Row 60. The word-level match means one mention reaches every 'Arjun' in the
    tenant — which is exactly how the leak would have surfaced in practice."""
    _tid, schema, ids, factory = seeded_people
    rows = await _lookup(factory, schema, ["arjun"], MINE)

    returned = {r["document_id"] for r in rows}
    assert ids["other"] not in returned
    assert ids["own"] in returned
    assert ids["system"] in returned


async def test_an_admin_sees_every_person(seeded_people):
    _tid, schema, ids, factory = seeded_people
    rows = await _lookup(factory, schema, ["arjun"], ADMIN)
    assert ids["other"] in {r["document_id"] for r in rows}


async def test_no_requesting_user_sees_source_system_people_only(seeded_people):
    """The widget path: an anonymous visitor must not resolve staff-uploaded people."""
    _tid, schema, ids, factory = seeded_people
    rows = await _lookup(factory, schema, ["arjun"], None)
    assert {r["document_id"] for r in rows} == {ids["system"]}


# --- The ADR-014 gap: conversation visibility on this path --------------------------


async def test_an_attachments_person_resolves_inside_its_own_conversation(seeded_people):
    _tid, schema, ids, factory = seeded_people
    rows = await _lookup(factory, schema, ["arjun attached"], MINE, CONV_A)
    assert [r["document_id"] for r in rows] == [ids["attached"]]


async def test_an_attachments_person_does_not_resolve_in_another_conversation(seeded_people):
    """The leak this closes: same user, same tenant, different conversation."""
    _tid, schema, ids, factory = seeded_people
    rows = await _lookup(factory, schema, ["arjun attached"], MINE, CONV_B)
    assert rows == []


async def test_an_attachments_person_does_not_resolve_with_no_conversation(seeded_people):
    """Fail closed, matching how the retriever treats a missing conversation."""
    _tid, schema, ids, factory = seeded_people
    rows = await _lookup(factory, schema, ["arjun attached"], MINE, None)
    assert rows == []


async def test_library_people_stay_visible_from_inside_a_conversation(seeded_people):
    """Conversation scoping must not hide tenant-library content, which is what
    `conversation_id IS NULL` means."""
    _tid, schema, ids, factory = seeded_people
    rows = await _lookup(factory, schema, ["arjun own"], MINE, CONV_A)
    assert [r["document_id"] for r in rows] == [ids["own"]]


async def test_both_rules_apply_together(seeded_people):
    """Neither predicate relaxes the other: inside conversation A, the requesting user
    sees their own library person, their own attachment, and source-system content —
    and never the other recruiter's."""
    _tid, schema, ids, factory = seeded_people
    rows = await _lookup(factory, schema, ["arjun"], MINE, CONV_A)

    assert {r["document_id"] for r in rows} == {ids["own"], ids["system"], ids["attached"]}


async def test_the_enrichment_read_is_scoped_too(seeded_people):
    """`_build_candidates` re-reads `document_entities` for the winning documents. It
    gets the same predicates rather than trusting that its caller filtered — the property
    that stops a future call site reintroducing the leak."""
    _tid, schema, ids, factory = seeded_people
    async with factory() as session:
        candidates = await entity_resolver._build_candidates(
            session, schema,
            [ids["own"], ids["other"], ids["attached"]],
            [
                {"document_id": ids["own"], "entity_value": "Arjun Own"},
                {"document_id": ids["other"], "entity_value": "Arjun Other"},
                {"document_id": ids["attached"], "entity_value": "Arjun Attached"},
            ],
            MINE, CONV_B,
        )

    enriched = {c.document_id for c in candidates if c.organization or c.experience or c.skills}
    assert ids["other"] not in enriched
    assert ids["attached"] not in enriched
