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
    def __init__(self):
        super().__init__(
            code="TENANT_MISMATCH",
            message="Token tenant does not match URL tenant",
            status_code=403,
        )


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
