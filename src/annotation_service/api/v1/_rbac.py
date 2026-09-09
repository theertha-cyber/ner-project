"""Role gates for annotation_service routes.

`TenantContextMiddleware` authenticates the JWT and pins `request.state.role`, but it
does not enforce *which* role may call *which* route — that is per-route, and before
this module it was applied inconsistently (only `review.py` had it). These helpers make
the check uniform.

The role taxonomy is the platform's four roles (see `gateway.models.UserRole`):
`system_admin`, `tenant_admin`, `annotator`, `business_user`. A `business_user` never
has annotation-administration or annotation-task access.
"""
from fastapi import HTTPException, Request

TENANT_ADMIN = "tenant_admin"
ANNOTATOR = "annotator"
SYSTEM_ADMIN = "system_admin"
BUSINESS_USER = "business_user"


def current_role(request: Request) -> str | None:
    return getattr(request.state, "role", None)


def require_roles(request: Request, *allowed: str) -> str:
    """Raise 403 unless the caller's role is one of `allowed`. Returns the role."""
    role = current_role(request)
    if role not in allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": f"This action requires one of: {', '.join(sorted(allowed))}",
            },
        )
    return role


def require_tenant_admin(request: Request) -> str:
    return require_roles(request, TENANT_ADMIN)


def require_annotator(request: Request) -> str:
    return require_roles(request, ANNOTATOR)


def require_annotator_or_tenant_admin(request: Request) -> str:
    return require_roles(request, ANNOTATOR, TENANT_ADMIN)
