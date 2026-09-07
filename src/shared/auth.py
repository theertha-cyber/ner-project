from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError, ExpiredSignatureError
from jose.exceptions import JWTClaimsError
from passlib.context import CryptContext
from src.shared.config import settings
from src.shared.exceptions import AuthError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not any(c.isupper() for c in password):
        return "Password must contain an uppercase letter"
    if not any(c.islower() for c in password):
        return "Password must contain a lowercase letter"
    if not any(c.isdigit() for c in password):
        return "Password must contain a digit"
    return None


def create_access_token(tenant_id: str, user_id: str, role: str, email: str = "") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": f"{tenant_id}:{user_id}",
        "tenant_id": tenant_id,
        "user_id": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(tenant_id: str, user_id: str, role: str, email: str = "") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": f"{tenant_id}:{user_id}",
        "tenant_id": tenant_id,
        "user_id": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_ttl_days),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_service_token(tenant_id: str, ttl_seconds: int = 60) -> str:
    """Short-lived, no-user token for server-to-server calls made on behalf of a
    tenant without an authenticated end-user session (e.g. the public/widget chat
    path calling model_serving's internal endpoints). Carries only `tenant_id` —
    no `user_id`/`role` — so it satisfies TenantContextMiddleware's tenant check
    without asserting any human identity or permission level."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": f"service:{tenant_id}",
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        "type": "service",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _count_auth_failure(reason: str) -> None:
    """Count one rejection under an enumerated reason.

    Function-local and guarded for the same reason as `TenantMismatchError`: this module
    is imported by code that runs before `init_observability`, and a token that cannot be
    validated because telemetry is not ready would be a far worse failure than a missing
    count.

    No token value or fragment is ever a label — the reason is drawn from the exception
    type, not from the token.
    """
    try:
        from src.shared.observability.domain_metrics import record_auth_failure

        record_auth_failure(reason)
    except Exception:
        pass


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except ExpiredSignatureError:
        _count_auth_failure("expired_token")
        raise AuthError("Token has expired")
    except JWTClaimsError:
        # Decoded and verified, rejected on a claim — a different operational fact from a
        # token that never parsed.
        _count_auth_failure("invalid_claims")
        raise AuthError("Invalid token")
    except JWTError as e:
        # `jose` raises the same `JWTError` for a token that failed signature verification
        # and one that was never a JWT at all. The two are worth telling apart: a wave of
        # signature failures is a key-rotation or an attack, a wave of malformed tokens is
        # a broken client. The message is inspected here and discarded — only the
        # enumerated reason leaves this function.
        reason = "invalid_signature" if "signature" in str(e).lower() else "malformed_token"
        _count_auth_failure(reason)
        raise AuthError("Invalid token")
