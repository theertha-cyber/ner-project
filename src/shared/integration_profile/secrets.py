"""The secret-reference resolution seam.

Resolution takes tenant identity *and* a reference, and the reference must be one the
tenant's own profile records — so holding a reference is not enough to read the secret it
names. Resolution happens once, at the edge, and the resolved values go into an immutable
tenant-bound context. An adapter receives values; it never receives a reference and never
receives a resolver, so there is no code path from adapter code to a secret source.

`AGENTS.md` requires secret-class settings to fail fast at startup. Per-tenant references
are created at run time and cannot be enumerated at process start, so this is an
acknowledged deviation rather than a silent exception: an unresolvable reference moves one
tenant's profile to `error` with an operator-visible reason, and the process keeps serving
every other tenant.
"""

import logging
import os
from dataclasses import dataclass
from typing import Mapping

from src.shared.integration_profile.config_schema import SECRET_REFERENCE_RE

logger = logging.getLogger(__name__)


class SecretResolutionError(Exception):
    """A reference that cannot be resolved.

    Carries a failure *class* and the reference, never a credential value and never a raw
    provider payload — the two things a resolution failure is most likely to be holding.
    """

    def __init__(self, reference: str, failure_class: str):
        self.reference = reference
        self.failure_class = failure_class
        super().__init__(f"secret reference '{reference}' unresolvable: {failure_class}")


@dataclass(frozen=True)
class TenantSecretContext:
    """Resolved values, bound to one tenant, immutable, and holding no resolver."""

    tenant_id: str
    values: Mapping[str, str]

    def get(self, field: str) -> str | None:
        return self.values.get(field)


class EnvironmentSecretResolver:
    """The one resolver this change ships: `env://NAME`.

    A real deployment substitutes a vault-backed resolver. The scheme is what selects it,
    so adding one is a registration rather than a change to any caller.
    """

    scheme = "env"

    def resolve(self, path: str) -> str:
        value = os.environ.get(path)
        if value is None:
            raise SecretResolutionError(f"{self.scheme}://{path}", "not_found")
        return value


_RESOLVERS = {EnvironmentSecretResolver.scheme: EnvironmentSecretResolver()}


def register_resolver(scheme: str, resolver) -> None:
    _RESOLVERS[scheme] = resolver


def _resolve_one(reference: str) -> str:
    if not isinstance(reference, str) or not SECRET_REFERENCE_RE.match(reference):
        raise SecretResolutionError(str(reference), "malformed_reference")
    scheme, _, path = reference.partition("://")
    resolver = _RESOLVERS.get(scheme)
    if resolver is None:
        raise SecretResolutionError(reference, "unknown_scheme")
    return resolver.resolve(path)


def resolve_for_tenant(profile, fields: list[str] | None = None) -> TenantSecretContext:
    """Resolve a tenant's own recorded references into a tenant-bound context.

    Only references read from `profile.secret_references` are resolvable, so a reference
    belonging to another tenant cannot be resolved by presenting it here.
    """
    references = dict(profile.secret_references or {})
    wanted = fields if fields is not None else list(references)

    resolved: dict[str, str] = {}
    for field in wanted:
        reference = references.get(field)
        if reference is None:
            raise SecretResolutionError(f"<{field}>", "not_recorded_for_tenant")
        resolved[field] = _resolve_one(reference)

    return TenantSecretContext(tenant_id=profile.tenant_id, values=resolved)


def sanitised_reason(error: SecretResolutionError) -> str:
    """The operator-visible reason recorded on an errored profile.

    Names the reference and the failure class. Contains no credential value, because none
    was ever obtained — that is the whole point of failing here.
    """
    return f"secret_reference={error.reference} failure={error.failure_class}"
