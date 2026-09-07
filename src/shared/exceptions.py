import logging

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


class TenantNotFoundError(AppError):
    def __init__(self, tenant_id: str):
        super().__init__(
            code="TENANT_NOT_FOUND",
            message=f"Tenant '{tenant_id}' not found",
            status_code=404,
        )


class TenantInactiveError(AppError):
    def __init__(self, tenant_id: str):
        super().__init__(
            code="TENANT_INACTIVE",
            message=f"Tenant '{tenant_id}' is deactivated",
            status_code=403,
        )


class TenantMismatchError(AppError):
    """A validated token asserting one tenant, addressing another.

    The counter and the log record live in the constructor rather than at the raise site
    (design Decision 4). There is exactly one raise site today —
    `src/gateway/dependencies.py` — and the value of this counter is entirely about the
    sites that do not exist yet: a new service, a new dependency, a new authorization
    path. A counter at the raise site is a convention the next author has to remember; a
    counter here cannot be raised without being counted.

    Neither tenant identifier is a metric label. The counter answers "is anyone attempting
    cross-tenant access"; *which* tenants is a question for the log record, where the
    foundation's redaction filter and the narrower access apply.
    """

    def __init__(self):
        super().__init__(
            code="TENANT_MISMATCH",
            message="Token tenant does not match URL tenant",
            status_code=403,
        )
        # Function-local and guarded: this module is imported by code that runs before
        # `init_observability`, and an exception type that cannot be constructed because
        # telemetry is not ready would be a far worse failure than a missing count.
        try:
            from src.shared.observability.domain_metrics import record_tenant_mismatch

            record_tenant_mismatch()
        except Exception:
            pass
        # WARNING rather than INFO: a non-zero rate here is an attempted cross-tenant
        # access, not an ordinary permission denial. The correlation fields —
        # request_id, tenant_id, trace_id — are attached by the foundation's logging
        # filter, so they are not repeated here.
        logger.warning("tenant_mismatch_rejected", extra={"code": "TENANT_MISMATCH"})


class QuotaExceededError(AppError):
    def __init__(self, resource: str, limit: int):
        super().__init__(
            code="QUOTA_EXCEEDED",
            message=f"{resource} quota exceeded (limit: {limit})",
            status_code=429,
        )


class AuthError(AppError):
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(code="AUTH_ERROR", message=message, status_code=401)


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} '{identifier}' not found",
            status_code=404,
        )


class ConflictError(AppError):
    def __init__(self, resource: str, field: str, value: str):
        super().__init__(
            code="CONFLICT",
            message=f"{resource} with {field} '{value}' already exists",
            status_code=409,
        )


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(code="VALIDATION_ERROR", message=message, status_code=422)
