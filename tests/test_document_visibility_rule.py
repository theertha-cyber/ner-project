"""Verification for the shared uploader-visibility rule — verification.md rows 1-5, 19.

The rule is the one the Documents library has always applied to listing. It lived only
there, so chat retrieval answered from documents the same user could not list. These
tests pin the predicate itself; the per-channel tests pin that each channel uses it.
"""

import re
from pathlib import Path

import pytest

from src.document_service.ingestion.contract import ActorKind
from src.shared.document_visibility import (
    HUMAN_ACTOR,
    NO_REQUESTING_USER,
    ROLE_TENANT_ADMIN,
    VISIBILITY_USER_PARAM,
    RequestingUser,
    is_unscoped,
    visibility_clause,
    visibility_predicate,
    visibility_predicate_via_document,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_human_actor_matches_the_ingestion_contract():
    """The rule compares against a literal, because importing the enum would close a
    cycle. That literal has to keep meaning what the ingestion contract means."""
    assert HUMAN_ACTOR == ActorKind.HUMAN.value


# --- Row 1: the user's own human-ingested document ---------------------------------


def test_predicate_admits_the_requesting_users_own_document():
    predicate, params = visibility_predicate(RequestingUser(user_id="u1", role="business_user"))
    assert predicate is not None
    assert "uploaded_by = :" + VISIBILITY_USER_PARAM in predicate
    assert params == {VISIBILITY_USER_PARAM: "u1"}


# --- Row 2: another user's human-ingested document ---------------------------------


def test_predicate_binds_the_user_rather_than_interpolating_it():
    """A formatted identifier is an injection surface and an un-cacheable plan."""
    predicate, params = visibility_predicate(RequestingUser(user_id="u2'; DROP TABLE documents--", role="business_user"))
    assert "DROP TABLE" not in predicate
    assert params[VISIBILITY_USER_PARAM] == "u2'; DROP TABLE documents--"


# --- Row 3: source-system content is tenant-wide -----------------------------------


def test_predicate_always_admits_non_human_ingestion():
    for user in (
        RequestingUser(user_id="u1", role="business_user"),
        NO_REQUESTING_USER,
    ):
        predicate, _ = visibility_predicate(user)
        assert f"ingested_by_kind <> '{HUMAN_ACTOR}'" in predicate


# --- Row 4: administrators are unscoped --------------------------------------------


def test_admin_is_unscoped():
    assert is_unscoped(ROLE_TENANT_ADMIN) is True
    assert is_unscoped("business_user") is False
    assert is_unscoped(None) is False

    predicate, params = visibility_predicate(RequestingUser(user_id="admin", role=ROLE_TENANT_ADMIN))
    assert predicate is None
    assert params == {}


def test_unscoped_is_none_not_an_empty_predicate():
    """`None` and `""` would both concatenate into valid SQL. Only one of them makes a
    caller that forgets the distinction fail loudly."""
    predicate, _ = visibility_predicate(RequestingUser(user_id="admin", role=ROLE_TENANT_ADMIN))
    assert predicate is None

    clause, _ = visibility_clause(RequestingUser(user_id="admin", role=ROLE_TENANT_ADMIN))
    assert clause == ""


# --- Row 19: no requesting user does not widen the rule ----------------------------


def test_absent_user_excludes_every_human_ingested_document():
    predicate, params = visibility_predicate(NO_REQUESTING_USER)
    assert predicate == f"ingested_by_kind <> '{HUMAN_ACTOR}'"
    assert params == {}
    assert "uploaded_by" not in predicate


def test_absent_user_is_not_treated_as_unscoped():
    """The failure this guards is a predicate written as `if user: filter`, where a
    missing identity silently becomes the widest possible visibility."""
    predicate, _ = visibility_predicate(NO_REQUESTING_USER)
    assert predicate is not None

    clause, _ = visibility_clause(NO_REQUESTING_USER)
    assert clause.strip().startswith("AND")


def test_none_user_behaves_as_no_requesting_user():
    assert visibility_predicate(None) == visibility_predicate(NO_REQUESTING_USER)


# --- Shape helpers -----------------------------------------------------------------


def test_prefix_qualifies_every_column():
    predicate, _ = visibility_predicate(RequestingUser(user_id="u1", role="business_user"), prefix="d.")
    assert "d.ingested_by_kind" in predicate
    assert "d.uploaded_by" in predicate
    assert re.search(r"(?<!d\.)\bingested_by_kind", predicate) is None


def test_via_document_wraps_the_predicate_in_a_document_subquery():
    predicate, params = visibility_predicate_via_document(
        RequestingUser(user_id="u1", role="business_user"), "document_id"
    )
    assert predicate.startswith("document_id IN (SELECT id FROM documents WHERE ")
    assert params == {VISIBILITY_USER_PARAM: "u1"}


def test_via_document_is_unrestricted_for_an_admin():
    predicate, params = visibility_predicate_via_document(
        RequestingUser(user_id="admin", role=ROLE_TENANT_ADMIN), "document_id"
    )
    assert predicate is None
    assert params == {}


def test_via_document_never_reaches_a_control_plane_table():
    """ADR-017: `documents` may resolve to a tenant-owned database, so the rule must be
    expressible inside the tenant schema alone."""
    predicate, _ = visibility_predicate_via_document(
        RequestingUser(user_id="u1", role="business_user"), "document_id"
    )
    assert "public." not in predicate
    assert "tenant_users" not in predicate


def test_clause_is_appendable_and_matches_the_predicate():
    user = RequestingUser(user_id="u1", role="business_user")
    predicate, predicate_params = visibility_predicate(user)
    clause, clause_params = visibility_clause(user)
    assert clause == f" AND {predicate}"
    assert clause_params == predicate_params


# --- Row 5: the rule has a single definition ---------------------------------------

# Where the literal condition is allowed to appear. Everything else must reach it through
# `src.shared.document_visibility`. The chunk-write path and the migration name the
# columns because they populate them; nothing else may re-derive the comparison.
_PREDICATE_DEFINITION_ALLOWLIST = {
    "src/shared/document_visibility.py",
    # Schema DDL, not a retrieval predicate. The partial index this revision creates is
    # the index the rule's queries use, so its WHERE clause has to spell out the same
    # comparison -- an index predicate cannot be built from a Python function. It is on
    # the same footing as the migration that creates it: it defines where the rule can
    # be evaluated quickly, never what the rule admits.
    "src/shared/tenant_store/revisions/006_document_chunks_uploader_visibility.py",
}
_COLUMN_WRITE_ALLOWLIST = {
    "src/shared/document_visibility.py",
    "src/shared/tenant_store/baseline.py",
    "src/document_service/ingestion/service.py",
    "src/document_service/services/ocr_worker.py",
    "src/document_service/api/v1/documents.py",
}


def _source_files():
    for path in (REPO_ROOT / "src").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path, path.relative_to(REPO_ROOT).as_posix()


def _code_only(source: str) -> str:
    """The file with comments and string literals removed.

    The guards below are about where the rule is *implemented*, not where it is
    explained. Several modules describe the denormalization in a comment, and a guard
    that forbade naming the columns in prose would push the explanation out of the files
    that most need it — the opposite of the intent.
    """
    import io
    import tokenize

    kept = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            kept.append(token.string)
    except (tokenize.TokenError, IndentationError):
        return source
    return "\n".join(kept)


def test_predicate_has_one_definition():
    """The comparison `ingested_by_kind <> 'human'` is the rule. Two copies of it is the
    defect this change exists to remove, and a third would reintroduce it silently."""
    offenders = []
    comparison = re.compile(r"ingested_by_kind\s*(<>|!=|=)\s*'")
    for path, rel in _source_files():
        if rel in _PREDICATE_DEFINITION_ALLOWLIST:
            continue
        if comparison.search(path.read_text(encoding="utf-8")):
            offenders.append(rel)
    assert offenders == [], (
        "the uploader-visibility comparison is written outside "
        f"src/shared/document_visibility.py in: {offenders}"
    )


def test_visibility_columns_are_named_only_where_they_are_populated_or_defined():
    """A file naming `uploaded_by` beside `ingested_by_kind` is either writing the
    columns or deciding visibility. The second is only allowed in one place."""
    offenders = []
    for path, rel in _source_files():
        if rel in _COLUMN_WRITE_ALLOWLIST:
            continue
        source = _code_only(path.read_text(encoding="utf-8"))
        if "ingested_by_kind" in source and "uploaded_by" in source:
            offenders.append(rel)
    assert offenders == [], (
        "both visibility columns are named outside the definition and the write paths "
        f"in: {offenders} — reach the rule through src.shared.document_visibility instead"
    )


@pytest.mark.parametrize(
    "module",
    [
        "src.shared.retrieval.retriever",
        "src.chat_api.services.sql_generator",
        "src.chat_api.services.entity_resolver",
        "src.document_service.api.v1.documents",
    ],
)
def test_every_channel_reaches_the_shared_definition(module):
    """Each channel that decides visibility imports the rule rather than restating it."""
    path = REPO_ROOT / (module.replace(".", "/") + ".py")
    source = path.read_text(encoding="utf-8")
    assert "document_visibility" in source, (
        f"{module} does not reference the shared uploader-visibility rule"
    )
