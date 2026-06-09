from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError, ExpiredSignatureError
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


def create_access_token(tenant_id: str, user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": f"{tenant_id}:{user_id}",
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(tenant_id: str, user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": f"{tenant_id}:{user_id}",
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_ttl_days),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except ExpiredSignatureError:
        raise AuthError("Token has expired")
    except JWTError:
        raise AuthError("Invalid token")
