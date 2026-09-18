"""The uploader-visibility rule, defined once.

A document is visible to a requesting user when no *human* ingested it — source-system
content is tenant-wide — or when the human who ingested it is that user. A tenant
administrator is unscoped. This is the rule the Documents library has always applied to
listing; this module is the single place it is written, so that listing and every chat
answer channel cannot drift apart. They already had: listing enforced the rule and no
answer channel did, which is the defect this module exists to prevent recurring.

Its own module, with no imports beyond the standard library, because the document
service, the chat service and `src/shared/retrieval` all need it and importing it from
any one of them would close a cycle — the same reason `document_retention` is its own
module. The values it compares against are the ones migration 038 constrains.

Callers get a predicate and its bound parameters, never a formatted value. Three shapes
are offered because the channels need three:

- `visibility_predicate` for a row that carries the denormalized columns itself
  (`document_chunks` after this change, and `documents`, where `id` is the document).
- `visibility_predicate_via_document` for a row that reaches a document through a
  foreign key (`document_entities`, `document_text_spans`, `extraction_runs`).
- `visibility_clause` for callers appending to an existing `WHERE`, matching the shape
  `_conversation_clause` already uses in the retriever.

A `None` predicate means "no restriction applies" — the administrator case. It is
deliberately not the empty string: a caller that concatenates blindly would produce
valid SQL either way, and the distinction between "unrestricted" and "restricted to
nothing" is the one worth being unable to get wrong by accident.
"""

from dataclasses import dataclass

# The ingesting-actor value that means a person, mirroring `ActorKind.HUMAN` in the
# ingestion contract. Restated here rather than imported for the cycle reason above;
# `tests/test_document_visibility_rule.py` asserts the two agree, so a divergence is a
# failing test rather than a silent visibility change.
HUMAN_ACTOR = "human"

# The one role the rule does not scope. Matches the role checked by `list_documents`.
ROLE_TENANT_ADMIN = "tenant_admin"

# The bound-parameter name every channel uses for the requesting user. Named distinctly
# so it cannot collide with a `user_id` parameter a caller already binds for its own
# reasons.
VISIBILITY_USER_PARAM = "visibility_user_id"


@dataclass(frozen=True)
class RequestingUser:
    """Who an answer is being produced for, taken from authenticated request state.

    Never constructed from a tool argument, a generated statement, or message text.
    `user_id` is None for a channel that has no end user at all — the embeddable
    widget, which answers under a tenant service identity.
    """

    user_id: str | None = None
    role: str | None = None

    @property
    def is_unscoped(self) -> bool:
        return is_unscoped(self.role)


# The absence of an end user, named so a caller states it rather than passing None and
# leaving a reader to guess whether that meant "anonymous" or "not wired up yet".
NO_REQUESTING_USER = RequestingUser(user_id=None, role=None)


def is_unscoped(role: str | None) -> bool:
    """Whether this role sees every document in the tenant regardless of ingesting actor."""
    return role == ROLE_TENANT_ADMIN


def visibility_predicate(
    user: RequestingUser | None,
    *,
    prefix: str = "",
    param_name: str = VISIBILITY_USER_PARAM,
) -> tuple[str | None, dict]:
    """The rule as a predicate over a row carrying `ingested_by_kind` and `uploaded_by`.

    `prefix` qualifies the columns for a statement that needs it (`d.`, or a template's
    placeholder). Returns `(None, {})` when the requesting user is unscoped.

    An absent `user_id` — no end user for this answer at all — admits source-system
    content only. It is emphatically not treated as "unscoped": the widest possible
    reading of a missing identity is the one failure a caller cannot detect, so the
    branch is written out here rather than falling out of a truthiness check at a call
    site.
    """
    if user is not None and user.is_unscoped:
        return None, {}

    not_human = f"{prefix}ingested_by_kind <> '{HUMAN_ACTOR}'"

    if user is None or user.user_id is None:
        return not_human, {}

    return (
        f"({not_human} OR {prefix}uploaded_by = :{param_name})",
        {param_name: user.user_id},
    )


def visibility_predicate_via_document(
    user: RequestingUser | None,
    link_column: str,
    *,
    documents_relation: str = "documents",
    param_name: str = VISIBILITY_USER_PARAM,
) -> tuple[str | None, dict]:
    """The rule for a row that reaches its document through `link_column`.

    `documents_relation` is unqualified by default for the same reason the conversation
    scope leaves it unqualified: the executing session's `search_path` is set to the
    tenant's schema, so it resolves there and nowhere else. Callers that do not set a
    `search_path` pass a schema-qualified name.

    The subquery stays inside the tenant schema deliberately. ADR-017 allows `documents`
    to resolve to a tenant-owned database, so the predicate may never reach a `public.*`
    control-plane table to discover who a user is.
    """
    predicate, params = visibility_predicate(user, param_name=param_name)
    if predicate is None:
        return None, {}
    return (
        f"{link_column} IN (SELECT id FROM {documents_relation} WHERE {predicate})",
        params,
    )


def visibility_clause(
    user: RequestingUser | None,
    *,
    prefix: str = "",
    param_name: str = VISIBILITY_USER_PARAM,
) -> tuple[str, dict]:
    """`visibility_predicate` as an appendable ` AND ...` fragment, or `("", {})`.

    The shape the retrievers want, matching `_conversation_clause` so the two guardrails
    read alike at the call site.
    """
    predicate, params = visibility_predicate(user, prefix=prefix, param_name=param_name)
    if predicate is None:
        return "", {}
    return f" AND {predicate}", params
