"""The declarations in `domain_metrics.py` are the cardinality and disclosure contract.

Verification rows 34, 35, 36 and 41, plus the structural evidence for the enumeration
requirement.

These tests read the declarations rather than the endpoint on purpose. The allowlist
requirement is that adding a tenant label to a *new* family fails the build, and a family
is only reachable on `/metrics` once some code path has actually recorded to it — so an
endpoint scan would pass for a family nobody exercised yet, which is exactly the family
nobody reviewed.
"""

import ast
import inspect
import pathlib

import pytest

from src.shared.observability import domain_metrics as dm

pytestmark = [pytest.mark.verification]


class TestTheTenantLabelAllowlist:
    """Rows 34, 35 and 36."""

    def test_an_allowlisted_family_may_carry_the_tenant_label(self):
        """Row 34 — the allowlist is permissive about what it names, not merely a denylist."""
        carrying = dm.families_carrying_tenant_label()

        assert carrying, "no family carries tenant_id — the allowlist would be vacuous"
        assert carrying <= dm.TENANT_LABEL_ALLOWLIST
        assert "ner_llm_tokens_total" in carrying, (
            "per-tenant consumption attribution is the one need that genuinely requires "
            "the label; if no family carries it the allowlist is not being exercised"
        )

    def test_a_family_not_on_the_list_carrying_the_label_fails_and_is_named(self):
        """Row 35 — the check must fail *and* say which family."""
        offender = dm.Family(
            "ner_unreviewed_thing_total",
            "counter",
            "a family nobody added to the allowlist",
            labels=(dm.tenant_label(),),
        )
        dm.FAMILIES[offender.name] = offender
        try:
            violations = dm.allowlist_violations()
        finally:
            del dm.FAMILIES[offender.name]

        assert violations == ["ner_unreviewed_thing_total"], (
            "an unnamed family carrying tenant_id must fail the check and identify itself"
        )

    def test_the_live_declarations_have_no_violation(self):
        """Row 35, the standing case — this is the assertion that goes red on a new label."""
        assert dm.allowlist_violations() == []

    def test_the_allowlist_is_explicit_and_small(self):
        """Row 36 — enumerated, not a pattern."""
        assert isinstance(dm.TENANT_LABEL_ALLOWLIST, frozenset)
        assert len(dm.TENANT_LABEL_ALLOWLIST) == 5

        for name in dm.TENANT_LABEL_ALLOWLIST:
            assert name in dm.FAMILIES, f"{name} is allowlisted but declared nowhere"
            assert "*" not in name and "?" not in name

    def test_the_allowlist_is_a_literal_set_in_the_source(self):
        """Row 36's teeth. A membership test passes just as happily against a
        comprehension over `startswith("ner_llm_")`, which would admit families nobody
        reviewed — the same mistake at one remove. So the source is parsed."""
        source = pathlib.Path(inspect.getfile(dm)).read_text(encoding="utf-8")
        tree = ast.parse(source)

        assignments = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign | ast.Assign)
            and any(
                getattr(t, "id", None) == "TENANT_LABEL_ALLOWLIST"
                for t in ([node.target] if isinstance(node, ast.AnnAssign) else node.targets)
            )
        ]
        assert len(assignments) == 1
        value = assignments[0].value

        assert isinstance(value, ast.Call) and getattr(value.func, "id", None) == "frozenset"
        literal = value.args[0]
        assert isinstance(literal, ast.Set), (
            "the allowlist must be a written-out set literal, not a comprehension, "
            "generator or pattern match"
        )
        assert all(isinstance(element, ast.Constant) for element in literal.elts)


class TestEveryLabelEnumeratesItsValues:
    """Structural evidence — the series count per family must be computable before
    shipping, not discovered when the endpoint gets slow."""

    def test_every_declared_label_has_a_finite_non_empty_value_set(self):
        for name, family in dm.FAMILIES.items():
            for label in family.labels:
                assert label.values, f"{name}.{label.name} declares no values"
                assert isinstance(label.values, frozenset)
                assert all(isinstance(v, str) for v in label.values)

    def test_the_only_open_label_is_the_allowlisted_tenant_label(self):
        """`tenant_id` is bounded by the tenant table rather than by a written-out set,
        which is precisely why it needs an allowlist and nothing else does."""
        open_labels = {
            (name, label.name)
            for name, family in dm.FAMILIES.items()
            for label in family.labels
            if isinstance(label, dm._TenantLabel)
        }

        assert {name for name, _ in open_labels} <= dm.TENANT_LABEL_ALLOWLIST
        assert all(label == "tenant_id" for _, label in open_labels)

    def test_the_total_series_count_is_computable_and_bounded(self):
        """The number this produces is the whole point of the enumeration rule. If it
        cannot be computed, the cardinality mitigation in design.md is not in force."""
        total = sum(family.series_count() for family in dm.FAMILIES.values())

        assert total > 0
        assert total < 5000, (
            f"declared series count is {total} before tenant multiplication — every "
            "enumerated label multiplies against every other on the same family"
        )

    def test_a_label_value_outside_its_set_is_coerced_rather_than_minting_a_series(self):
        label = dm.Label("stage", frozenset({"parse", dm.OTHER}))

        assert label.coerce("parse") == "parse"
        assert label.coerce("a stage nobody declared") == dm.OTHER
        assert label.coerce(None) == dm.OTHER


class TestNoEntityTypeLabel:
    """Row 41 — design Decision 12.

    Entity types are tenant-configured (`src/gateway/api/v1/entity_types.py` exposes
    `list_entity_types(tenant_id)`), so they are neither enumerable at declaration nor
    safe in a store shared across tenants: a tenant that configures `policy_holder` and
    `claim_number` is identifiable from label values alone. That routes around the tenant
    allowlist rather than violating it, which makes it the harder failure to notice.
    """

    FORBIDDEN = ("entity_type", "entity_types", "entity_name", "entity_label", "label_type")

    def test_no_declared_family_carries_an_entity_type_label(self):
        offenders = [
            f"{name}.{label.name}"
            for name, family in dm.FAMILIES.items()
            for label in family.labels
            if label.name in self.FORBIDDEN
        ]

        assert offenders == [], (
            "entity types are tenant-authored; per-type detail belongs on the run's span, "
            f"which is tenant-scoped and covered by the release-gate scan: {offenders}"
        )

    def test_the_aggregate_entity_counter_is_declared_with_no_labels_at_all(self):
        family = dm.FAMILIES["ner_extraction_entities_total"]

        assert family.labels == (), (
            "the aggregate count is the metric; ADR-010's per-type granularity is "
            "preserved on the span, where it is actually queried"
        )
