"""A caller-supplied `X-Request-ID` is a correlation value and nothing else.

Verification row 9.

Accepting the inbound header is what makes support workflows possible — a caller can join
their own logs to ours. The cost of accepting it is that a client now controls a value
that flows into log records and response headers, so the boundary has to be explicit:
tenant and user identity continue to derive from the validated JWT claims alone, and the
identifier is sanitised before it is used anywhere.

Under ADR-001's model, a client-controlled input reaching a tenancy decision is the whole
failure mode, so this is pinned rather than assumed from reading the middleware.
"""

import inspect

import httpx
import pytest
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.observability import ObservabilityMiddleware
from src.shared.observability import middleware as shared_middleware
from src.shared.observability.context import get_request_id, get_tenant_id, set_tenant_id

pytestmark = [pytest.mark.verification]

CLAIMED_TENANT = "3f2a91c4-77bd-4f1e-9c2a-0e5b8d6a1f30"
FORGED = "victim-tenant-11111111-1111-1111-1111-111111111111"

SERVICES = (
    "gateway",
    "chat_api",
    "document_service",
    "extraction_service",
    "model_serving",
    "training_service",
    "annotation_service",
    "analytics_service",
)


class _JwtOnlyTenantMiddleware(BaseHTTPMiddleware):
    """Resolves tenancy from the token claim, exactly as each service's own middleware
    does, and from nothing else."""

    async def dispatch(self, request: Request, call_next):
        claims = {"tenant_id": CLAIMED_TENANT, "user_id": "user-1"}
        set_tenant_id(claims["tenant_id"])
        return await call_next(request)


@pytest.fixture
def app():
    application = FastAPI()

    @application.get("/whoami")
    async def whoami():
        return {"tenant_id": get_tenant_id(), "request_id": get_request_id()}

    application.add_middleware(_JwtOnlyTenantMiddleware)
    application.add_middleware(ObservabilityMiddleware)
    return application


async def _get(app, headers=None):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        return await client.get("/whoami", headers=headers or {})


class TestTheHeaderDoesNotInfluenceIdentity:
    async def test_a_forged_identifier_does_not_change_the_resolved_tenant(self, app):
        response = await _get(app, headers={"X-Request-ID": FORGED})

        assert response.json()["tenant_id"] == CLAIMED_TENANT

    async def test_the_forged_value_is_still_used_for_correlation(self, app):
        """The point is that it is accepted *as a correlation value* — a test that
        passed by rejecting the header would be testing the wrong fix."""
        response = await _get(app, headers={"X-Request-ID": "support-case-9182"})

        assert response.json()["request_id"] == "support-case-9182"
        assert response.headers["X-Request-ID"] == "support-case-9182"


class TestTheSharedMiddlewareMakesNoSecurityDecision:
    """Risk-register item 1: the consolidation must not have absorbed access control."""

    def test_it_does_not_decode_tokens_or_resolve_tenants(self):
        source = inspect.getsource(shared_middleware)

        for forbidden in ("decode_token", "Authorization", "tenant_id", "widget_api_keys"):
            assert forbidden not in source, (
                f"`{forbidden}` in the shared correlation middleware means an "
                "observability change now owns part of tenant enforcement"
            )

    @pytest.mark.parametrize("service", SERVICES)
    def test_each_service_still_owns_its_own_authorization(self, service):
        from pathlib import Path

        path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / service
            / "middleware"
            / "tenant_context.py"
        )
        source = path.read_text(encoding="utf-8")

        assert "Authorization" in source
        assert "exempt_paths" in source or "PUBLIC_PATHS" in source
