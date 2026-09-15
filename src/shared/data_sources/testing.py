"""The secure connection-test seam (CAP-2).

A test resolves the connection's secret references, then proves TLS-validated
connectivity to the provider endpoint without transmitting credentials and without
retaining anything but a finite outcome class. The shipped implementation performs
a TCP connect plus TLS handshake against the provider endpoint with a short
timeout; provider SDK calls, which would need the credential on the wire, are
deliberately out of scope for the test path.

Azure is not reachable from every environment this code runs in, and live Azure
verification is deferred per run provisioning — so the tester is a registered
seam, exactly like the secret resolvers in
`src.shared.integration_profile.secrets`: tests and local fixtures register a
fake per provider, production registers SDK-backed testers. An unregistered
provider fails closed with `connection_failed`, never open.
"""

import logging
import socket
import ssl
from dataclasses import dataclass

from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources.providers import (
    PROVIDER_AZURE_BLOB,
    PROVIDER_AZURE_POSTGRESQL,
    PROVIDER_AZURE_POSTGRESQL_DATA_PLANE,
)

logger = logging.getLogger(__name__)

TEST_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class SecureTestResult:
    """The finite result of one secure connection test."""

    passed: bool
    reason_code: str


_TESTERS: dict[str, object] = {}


def register_tester(provider: str, tester) -> None:
    """Register (or replace) the tester for one provider. Fakes use this too."""
    _TESTERS[provider] = tester


def _endpoint_for(provider: str, configuration: dict) -> tuple[str, int]:
    if provider == PROVIDER_AZURE_BLOB:
        return f"{configuration['account'].strip()}.blob.core.windows.net", 443
    return configuration["host"].strip(), int(configuration["port"])


class TlsHandshakeTester:
    """The shipped tester: TCP connect plus TLS handshake, credentials never sent.

    A passed handshake proves the endpoint is reachable over validated TLS. It
    does not authenticate — authentication failures at test time would require
    sending the credential, which the test path must not do — so a passed test
    means "reachable and TLS-valid", and activation additionally requires a
    resolvable secret reference plus customer evidence.
    """

    async def run(
        self, provider: str, configuration: dict, secret_values: dict
    ) -> SecureTestResult:
        try:
            host, port = _endpoint_for(provider, configuration)
        except (KeyError, TypeError, ValueError):
            return SecureTestResult(False, lc.TEST_REASON_VALIDATION_FAILED)
        try:
            context = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=TEST_TIMEOUT_SECONDS) as raw:
                with context.wrap_socket(raw, server_hostname=host):
                    pass
        except ssl.SSLCertVerificationError:
            return SecureTestResult(False, lc.TEST_REASON_TLS_VALIDATION_FAILED)
        except (socket.timeout, TimeoutError, ConnectionError, OSError):
            return SecureTestResult(False, lc.TEST_REASON_CONNECTION_FAILED)
        except Exception:
            logger.debug(
                "secure_test_failed",
                extra={"provider": provider, "reason": lc.TEST_REASON_CONNECTION_FAILED},
            )
            return SecureTestResult(False, lc.TEST_REASON_CONNECTION_FAILED)
        return SecureTestResult(True, lc.TEST_REASON_NONE)


register_tester(PROVIDER_AZURE_BLOB, TlsHandshakeTester())
register_tester(PROVIDER_AZURE_POSTGRESQL, TlsHandshakeTester())


def _register_data_plane_tester() -> None:
    # Deferred import: data_plane_tester.py imports psycopg2 and this module, so a
    # module-level import here would be circular (testing.py -> data_plane_tester.py
    # -> testing.py for SecureTestResult).
    from src.shared.data_sources.data_plane_tester import DataPlaneSecureTester

    register_tester(PROVIDER_AZURE_POSTGRESQL_DATA_PLANE, DataPlaneSecureTester())


_register_data_plane_tester()


async def run_secure_test(
    provider: str,
    configuration: dict,
    secret_values: dict,
    tenant_id: str | None = None,
    expected_store_id: str | None = None,
) -> SecureTestResult:
    """Run the registered tester. Unknown providers fail closed.

    `tenant_id` and `expected_store_id` are passed only to testers that declare
    them (inspected, not assumed) — the shared TLS-handshake tester and every fake
    registered in tests have no use for either, and the ADR-017 data-plane tester
    needs `tenant_id` for its target-schema check and `expected_store_id` for the
    replacement/credential-rotation identity check (tenant-residency-store-
    provisioning spec).
    """
    tester = _TESTERS.get(provider)
    if tester is None:
        return SecureTestResult(False, lc.TEST_REASON_CONNECTION_FAILED)
    import inspect

    params = inspect.signature(tester.run).parameters
    kwargs = {}
    if "tenant_id" in params:
        kwargs["tenant_id"] = tenant_id
    if "expected_store_id" in params:
        kwargs["expected_store_id"] = expected_store_id
    result = await tester.run(provider, configuration, secret_values, **kwargs)
    if result.reason_code not in lc.TEST_REASONS:
        # A custom tester returning an undeclared class is a contract violation;
        # coerce to the safe failure rather than persisting an open vocabulary.
        return SecureTestResult(False, lc.TEST_REASON_CONNECTION_FAILED)
    return result
