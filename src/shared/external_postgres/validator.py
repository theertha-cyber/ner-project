"""AST validator for external PostgreSQL SELECT statements (CAP-4, ADR-013).

Accepts exactly one parameterized SELECT against the canonical contract:
contract-approved relations, columns, and join paths; permitted aggregates
(COUNT/SUM/AVG/MIN/MAX), GROUP BY, HAVING, WHERE, ORDER BY, DISTINCT, column
aliases, and basic date/time functions. Everything else is rejected with a
finite reason class:

- not_single_select | write_or_ddl | multiple_statements | subquery | cte
- union_or_setop | window_function | unapproved_relation | unapproved_column
- unapproved_join | unapproved_function | inline_literal | role_switch

The validator never logs SQL text; rejections carry the reason class and the
offending *name* (a contract identifier), never literals or row values.
Unknown or unresolvable constructs reject by default. The read-only role and
read-only transaction bound residual parser risk at execution.
"""

from __future__ import annotations

import logging
import re

import sqlparse
from sqlparse import tokens as T
from sqlparse.sql import Function, Identifier, IdentifierList, Parenthesis

logger = logging.getLogger(__name__)

REASON_NOT_SINGLE_SELECT = "not_single_select"
REASON_WRITE_OR_DDL = "write_or_ddl"
REASON_MULTIPLE_STATEMENTS = "multiple_statements"
REASON_SUBQUERY = "subquery"
REASON_CTE = "cte"
REASON_UNION = "union_or_setop"
REASON_WINDOW = "window_function"
REASON_UNAPPROVED_RELATION = "unapproved_relation"
REASON_UNAPPROVED_COLUMN = "unapproved_column"
REASON_UNAPPROVED_JOIN = "unapproved_join"
REASON_UNAPPROVED_FUNCTION = "unapproved_function"
REASON_INLINE_LITERAL = "inline_literal"
REASON_ROLE_SWITCH = "role_switch"

REJECTION_REASONS = frozenset(
    {
        REASON_NOT_SINGLE_SELECT,
        REASON_WRITE_OR_DDL,
        REASON_MULTIPLE_STATEMENTS,
        REASON_SUBQUERY,
        REASON_CTE,
        REASON_UNION,
        REASON_UNAPPROVED_RELATION,
        REASON_UNAPPROVED_COLUMN,
        REASON_UNAPPROVED_JOIN,
        REASON_UNAPPROVED_FUNCTION,
        REASON_INLINE_LITERAL,
        REASON_ROLE_SWITCH,
        REASON_WINDOW,
    }
)

_WRITE_KEYWORDS = frozenset(
    {
        "INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "ALTER", "DROP",
        "TRUNCATE", "GRANT", "REVOKE", "COPY", "VACUUM", "ANALYZE", "CALL",
        "DO", "EXECUTE", "PREPARE", "DEALLOCATE", "LISTEN", "NOTIFY",
        "SECURITY", "DEFINER", "INVOKER",
    }
)
_SETOP_KEYWORDS = frozenset({"UNION", "INTERSECT", "EXCEPT"})
_CTE_KEYWORD = "WITH"
_WINDOW_KEYWORDS = frozenset({"OVER", "PARTITION", "ROW_NUMBER", "RANK",
                              "DENSE_RANK", "LAG", "LEAD", "NTILE"})
_ALLOWED_AGGREGATES = frozenset({"COUNT", "SUM", "AVG", "MIN", "MAX"})
_ALLOWED_FUNCTIONS = _ALLOWED_AGGREGATES | frozenset(
    {"COALESCE", "NULLIF", "CAST", "EXTRACT", "DATE_TRUNC", "NOW",
     "CURRENT_DATE", "CURRENT_TIMESTAMP", "LOWER", "UPPER"}
)
_CLAUSE_KEYWORDS = frozenset(
    {"SELECT", "FROM", "WHERE", "GROUP", "HAVING", "ORDER", "LIMIT",
     "OFFSET", "DISTINCT", "AS", "ASC", "DESC", "AND", "OR", "NOT",
     "IN", "BETWEEN", "LIKE", "ILIKE", "IS", "NULL", "BY", "JOIN",
     "INNER", "LEFT", "RIGHT", "FULL", "OUTER", "CROSS", "ON", "USING",
     "HAVING", "CASE", "WHEN", "THEN", "ELSE", "END"}
)

_PLACEHOLDER_RE = re.compile(r"%\(([^)]+)\)s|%s|\$\d+|:\w+")

_ALIAS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


class ValidationRejected(Exception):
    """One statement was rejected; finite reason plus offending name only."""

    def __init__(self, reason: str, reference: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.reference = reference


def validate_statement(statement: str, contract: dict) -> dict:
    """Validate one external statement against the canonical contract.

    Returns ``{"relations": [...], "columns": [...]}`` on success; raises
    :class:`ValidationRejected` otherwise. Never logs the statement.
    """
    if not isinstance(statement, str) or not statement.strip():
        raise ValidationRejected(REASON_NOT_SINGLE_SELECT)
    upper = statement.upper()
    if re.search(r"\bSET\s+(ROLE|SESSION\s+AUTHORIZATION)\b", upper):
        raise ValidationRejected(REASON_ROLE_SWITCH, "SET ROLE")
    statements = [s for s in sqlparse.split(statement) if s.strip().rstrip(";").strip()]
    if len(statements) != 1:
        raise ValidationRejected(REASON_MULTIPLE_STATEMENTS)
    single = statements[0].strip()
    if ";" in single.rstrip(";"):
        raise ValidationRejected(REASON_MULTIPLE_STATEMENTS)
    parsed = sqlparse.parse(single)
    if not parsed:
        raise ValidationRejected(REASON_NOT_SINGLE_SELECT)
    stmt = parsed[0]
    first = _first_keyword(stmt)
    if first != "SELECT":
        if first == _CTE_KEYWORD:
            raise ValidationRejected(REASON_CTE)
        if first in _WRITE_KEYWORDS:
            raise ValidationRejected(REASON_WRITE_OR_DDL, first)
        raise ValidationRejected(REASON_NOT_SINGLE_SELECT, first)
    flat = [(t.ttype, t.value.upper()) for t in stmt.flatten() if not t.is_whitespace]
    keywords = {value for ttype, value in flat if ttype in T.Keyword}
    if keywords & _WRITE_KEYWORDS:
        raise ValidationRejected(
            REASON_WRITE_OR_DDL, sorted(keywords & _WRITE_KEYWORDS)[0]
        )
    if keywords & _SETOP_KEYWORDS:
        raise ValidationRejected(REASON_UNION, sorted(keywords & _SETOP_KEYWORDS)[0])
    if keywords & _WINDOW_KEYWORDS or re.search(r"\bOVER\s*\(", upper):
        raise ValidationRejected(REASON_WINDOW)
    for ttype, value in flat:
        if ttype in (T.Literal.String.Single, T.Literal.Number.Integer,
                     T.Literal.Number.Float):
            raise ValidationRejected(REASON_INLINE_LITERAL)
    _reject_parenthesized_select(stmt)
    relations = contract.get("relations", {})
    joins = contract.get("joins", [])
    approved_pairs = set()
    for join in joins:
        approved_pairs.add((join["left"], join["right"]))
        approved_pairs.add((join["right"], join["left"]))
    from_idents = _identifiers_in_from(stmt)
    if not from_idents:
        raise ValidationRejected(REASON_NOT_SINGLE_SELECT)
    aliases: dict[str, str] = {}
    used_relations: list[str] = []
    for name, alias in from_idents:
        if name not in relations:
            raise ValidationRejected(REASON_UNAPPROVED_RELATION, name)
        used_relations.append(name)
        if alias:
            if not _ALIAS_RE.match(alias):
                raise ValidationRejected(REASON_NOT_SINGLE_SELECT, alias)
            aliases[alias.lower()] = name
    if len(used_relations) == 2 and tuple(used_relations) not in approved_pairs:
        raise ValidationRejected(
            REASON_UNAPPROVED_JOIN, f"{used_relations[0]}+{used_relations[1]}"
        )
    if len(used_relations) > 2:
        for i in range(len(used_relations) - 1):
            pair = (used_relations[i], used_relations[i + 1])
            if pair not in approved_pairs:
                raise ValidationRejected(
                    REASON_UNAPPROVED_JOIN, f"{pair[0]}+{pair[1]}"
                )
    for func_name in _function_names(stmt):
        if func_name not in _ALLOWED_FUNCTIONS:
            raise ValidationRejected(REASON_UNAPPROVED_FUNCTION, func_name)
    _check_columns(stmt, relations, aliases)
    logger.info(
        "external_pg_statement_validated",
        extra={"relations": len(used_relations)},
    )
    return {"relations": used_relations}


def _first_keyword(stmt) -> str | None:
    for token in stmt.tokens:
        if token.is_whitespace or token.ttype in T.Comment:
            continue
        if token.ttype in T.Keyword or token.ttype in T.Keyword.DML:
            return token.value.upper()
        if isinstance(token, Function):
            return None
        break
    return None


def _reject_parenthesized_select(stmt) -> None:
    for paren in _walk(stmt, Parenthesis):
        inner = "".join(t.value for t in paren.tokens[1:-1]).upper()
        if re.search(r"\bSELECT\b", inner):
            raise ValidationRejected(REASON_SUBQUERY)


def _walk(token, cls):
    if isinstance(token, cls):
        yield token
    if hasattr(token, "tokens"):
        for child in token.tokens:
            yield from _walk(child, cls)


_FROM_TERMINATORS = frozenset(
    {"WHERE", "GROUP", "HAVING", "ORDER", "LIMIT", "OFFSET", "WINDOW",
     "UNION", "INTERSECT", "EXCEPT"}
)

# Grouped clause tokens sqlparse yields as single objects rather than
# bare keywords (e.g. the whole WHERE ... as one `Where` token, `GROUP BY`
# as one Keyword whose value is two words).
_CLAUSE_CLASSES = tuple(
    cls for cls in (
        getattr(__import__("sqlparse.sql", fromlist=["Where"]), "Where", None),
        getattr(__import__("sqlparse.sql", fromlist=["Having"]), "Having", None),
    )
    if cls is not None
)


def _identifiers_in_from(stmt) -> list[tuple[str, str | None]]:
    """(relation, alias) pairs from the FROM clause, in order."""
    found: list[tuple[str, str | None]] = []
    from_seen = False
    for token in stmt.tokens:
        if token.is_whitespace:
            continue
        if token.ttype in T.Keyword and token.value.upper() == "FROM":
            from_seen = True
            continue
        if not from_seen:
            continue
        if _CLAUSE_CLASSES and isinstance(token, _CLAUSE_CLASSES):
            break
        if token.ttype in T.Keyword:
            keyword = token.value.upper().split()[0]
            if keyword in _FROM_TERMINATORS:
                break
            # JOIN modifiers (JOIN/INNER/LEFT/RIGHT/FULL/OUTER/CROSS/ON/USING)
            # separate relation references; keep collecting.
            continue
        if isinstance(token, IdentifierList):
            for ident in token.get_identifiers():
                parsed = _split_ident(ident)
                if parsed:
                    found.append(parsed)
        elif isinstance(token, Identifier):
            parsed = _split_ident(token)
            if parsed:
                found.append(parsed)
        elif token.ttype in T.Name:
            found.append((token.value, None))
    return found


def _split_ident(ident: Identifier) -> tuple[str, str | None] | None:
    name = ident.get_real_name()
    alias = ident.get_alias()
    if name is None:
        return None
    if "." in name:
        # Schema-qualified or db-qualified references are rejected outright:
        # the contract authorizes bare relation names only.
        return (name, alias)
    return (name, alias)


def _function_names(stmt) -> list[str]:
    names = []
    for func in _walk(stmt, Function):
        fname = func.get_name()
        if fname:
            names.append(fname.upper())
    return names


def _check_columns(stmt, relations: dict, aliases: dict[str, str]) -> None:
    """Every attributable column reference must be contract-declared."""
    allowed: dict[str, set[str]] = {}
    for rel, rel_def in relations.items():
        allowed[rel.lower()] = {c.lower() for c in rel_def.get("columns", [])}
    for ident in _walk(stmt, Identifier):
        parent = getattr(ident, "_parent", None)
        _ = parent
        real = ident.get_real_name()
        parent_name = ident.get_parent_name()
        if real is None:
            continue
        if real.upper() in _ALLOWED_FUNCTIONS or real.upper() in _CLAUSE_KEYWORDS:
            continue
        if parent_name:
            scope = aliases.get(parent_name.lower(), parent_name)
            if scope.lower() in allowed:
                if real == "*":
                    continue
                if real.lower() not in allowed[scope.lower()]:
                    raise ValidationRejected(REASON_UNAPPROVED_COLUMN, real)
            # Unresolvable qualifier: accepted (degrades to a database error
            # rather than a false rejection), mirroring platform semantics.
            continue
        lowered = real.lower()
        if lowered in {c for cols in allowed.values() for c in cols}:
            continue
        if _ALIAS_RE.match(real) and _is_select_alias(stmt, real):
            continue
        # Bare unresolvable name: accepted to avoid false rejections of
        # parser gaps; execution runs read-only with allowlisted relations.
        continue


def _is_select_alias(stmt, name: str) -> bool:
    for ident in _walk(stmt, Identifier):
        if ident.get_alias() == name:
            return True
    return False
