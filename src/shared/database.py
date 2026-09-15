import ssl
from collections import OrderedDict
from urllib.parse import quote

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_exponential

from src.shared.config import settings
from src.shared.data_plane import (
    DATA_PLANE_SECRET_KIND,
    DataPlaneNotReady,
    DataPlaneUnavailable,
    get_data_plane_record,
    get_data_plane_record_sync,
)
_engine = None
_sync_platform_engine = None

_CONNECTIONS_TABLE = "public.tenant_data_source_connections"


class _ConnectionSecretShim:
    """The minimal shape `resolve_for_tenant` needs — a tenant id and a
    `{kind: {field: reference}}` map — built from a connection row rather than an
    integration profile, matching `src/shared/tenant_store/migrate.py`'s shim."""

    def __init__(self, tenant_id: str, secret_references: dict):
        self.tenant_id = tenant_id
        self.secret_references = secret_references


def _connection_url(configuration: dict, password: str, *, async_driver: bool) -> str:
    scheme = "postgresql+asyncpg" if async_driver else "postgresql"
    # Real Azure-generated passwords routinely carry `@`, `/`, `:`, `%` — unescaped,
    # any of those splits the URL's userinfo/host boundary in the wrong place (a
    # password ending in `...3@` before the real `@host` separator leaves a stray
    # `3@` prefixed onto the hostname the driver actually tries to resolve).
    return (
        f"{scheme}://{quote(configuration['username'], safe='')}:{quote(password, safe='')}@"
        f"{configuration['host']}:{configuration['port']}/{configuration['database']}"
    )


def _ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def _asyncpg_connect_args(configuration: dict) -> dict:
    """`verify-full` is what every real `azure_postgresql_data_plane` connection
    carries (`providers.py` fixes it at creation, group 7) — a hostname-verified TLS
    context. A stored `sslmode` other than `verify-full` only reaches here through a
    row a test inserted directly, bypassing that validation, to exercise the resolver
    against the untrusted-cert local Compose stand-in (Design D11)."""
    args = {
        "timeout": settings.data_plane_connect_timeout_seconds,
        "server_settings": {"statement_timeout": str(settings.data_plane_statement_timeout_ms)},
    }
    sslmode = configuration.get("sslmode", "verify-full")
    if sslmode != "disable":
        args["ssl"] = _ssl_context()
    return args


def system_ca_bundle_path() -> str | None:
    """The real on-disk CA bundle this interpreter's OpenSSL trusts by default.

    `psycopg2-binary` links its own static OpenSSL, whose compiled-in default cert
    path does not necessarily match the container's actual system path — so libpq's
    own `sslrootcert=system` (added in libpq 15) resolves against the *wrong*
    OpenSSL's defaults and fails `verify-full` even when the real CA is present on
    disk. Resolving the path via the stdlib `ssl` module (tied to the system
    OpenSSL the interpreter itself is linked against) and passing it explicitly
    sidesteps that mismatch."""
    return ssl.get_default_verify_paths().cafile


def _psycopg2_connect_args(configuration: dict) -> dict:
    sslmode = configuration.get("sslmode", "verify-full")
    args = {
        "sslmode": sslmode,
        "connect_timeout": int(settings.data_plane_connect_timeout_seconds),
        "options": f"-c statement_timeout={settings.data_plane_statement_timeout_ms}",
    }
    if sslmode not in ("disable", "allow", "prefer"):
        cafile = system_ca_bundle_path()
        if cafile:
            args["sslrootcert"] = cafile
    return args


class _EngineLRU:
    """A bounded LRU of tenant-store engines, keyed by `(tenant_id, connection_id,
    connection.updated_at)` (Design D4) so a credential rotation or replacement
    transparently invalidates the old key without an explicit eviction call — the new
    resolution simply misses and builds a fresh engine under the new key."""

    def __init__(self, max_size: int):
        self._max_size = max_size
        self._entries: "OrderedDict[tuple, object]" = OrderedDict()

    def get(self, key: tuple):
        engine = self._entries.get(key)
        if engine is not None:
            self._entries.move_to_end(key)
        return engine

    def put(self, key: tuple, engine) -> object | None:
        """Stores `engine` under `key`; returns an evicted engine (oldest, over
        capacity) for the caller to dispose, or `None`."""
        self._entries[key] = engine
        self._entries.move_to_end(key)
        evicted = None
        if len(self._entries) > self._max_size:
            _, evicted = self._entries.popitem(last=False)
        return evicted

    def pop_all_for_tenant(self, tenant_id: str) -> list:
        stale_keys = [k for k in self._entries if k[0] == tenant_id]
        return [self._entries.pop(k) for k in stale_keys]


class EngineResolver:
    """The single place a tenant's engine is chosen (ADR-017, Design D4).

    - `tenant_id is None` -> the platform engine (control-plane access).
    - `mode = platform` -> the platform engine.
    - `mode = tenant_owned`, `status = ready` -> a cached per-tenant engine built from
      the tenant's active `azure_postgresql_data_plane` connection, TLS `verify-full`,
      a bounded pool, and connect/statement timeouts.
    - Any other status, or a connection that cannot be resolved -> a typed error.
      **Never** the platform engine for a `tenant_owned` tenant.
    """

    def __init__(self):
        self._async_lru = _EngineLRU(settings.data_plane_max_cached_engines)
        self._sync_lru = _EngineLRU(settings.data_plane_max_cached_engines)

    def _platform_engine(self):
        global _engine
        if _engine is None:
            _engine = create_async_engine(settings.database_url, poolclass=NullPool)
        return _engine

    def _platform_sync_engine(self):
        global _sync_platform_engine
        if _sync_platform_engine is None:
            _sync_platform_engine = create_engine(settings.database_url_sync, poolclass=NullPool)
        return _sync_platform_engine

    # --- shared connection-row + secret resolution -----------------------------

    def _fetch_connection_row(self, conn, connection_id: str):
        stmt = text(
            f"SELECT configuration, secret_references, updated_at "
            f"FROM {_CONNECTIONS_TABLE} WHERE id = :id AND status = 'active'"
        )
        result = conn.execute(stmt, {"id": connection_id})
        return result.fetchone()

    async def _fetch_connection_row_async(self, conn, connection_id: str):
        stmt = text(
            f"SELECT configuration, secret_references, updated_at "
            f"FROM {_CONNECTIONS_TABLE} WHERE id = :id AND status = 'active'"
        )
        result = await conn.execute(stmt, {"id": connection_id})
        return result.fetchone()

    def _resolve_password(self, tenant_id: str, secret_references: dict) -> str:
        # Deferred: `src.shared.integration_profile` eagerly imports a chain that ends
        # at `src.document_service.services.ocr_worker`, which imports `get_engine`
        # from this module — a module-level import here would be circular.
        from src.shared.integration_profile.secrets import SecretResolutionError, resolve_for_tenant

        try:
            secrets = resolve_for_tenant(
                _ConnectionSecretShim(tenant_id, {DATA_PLANE_SECRET_KIND: secret_references}),
                DATA_PLANE_SECRET_KIND,
            )
        except SecretResolutionError as exc:
            raise DataPlaneUnavailable("secret_unresolvable") from exc
        password = secrets.get("password_ref")
        if not password:
            raise DataPlaneUnavailable("secret_unresolvable")
        return password

    # --- async path --------------------------------------------------------------

    async def resolve(self, tenant_id: str | None = None):
        if tenant_id is None:
            return self._platform_engine()

        platform_engine = self._platform_engine()
        async with platform_engine.connect() as conn:
            record = await get_data_plane_record(tenant_id, conn)

            if record.is_platform:
                return self._platform_engine()

            if record.status != "ready":
                raise DataPlaneNotReady(record.status)

            if not record.connection_id:
                raise DataPlaneUnavailable("connection_missing")

            row = await self._fetch_connection_row_async(conn, record.connection_id)

        if row is None:
            raise DataPlaneUnavailable("connection_missing")

        cache_key = (tenant_id, record.connection_id, row.updated_at.isoformat() if row.updated_at else "")
        cached = self._async_lru.get(cache_key)
        if cached is not None:
            return cached

        configuration = row.configuration or {}
        password = self._resolve_password(tenant_id, row.secret_references or {})
        try:
            engine = create_async_engine(
                _connection_url(configuration, password, async_driver=True),
                pool_size=settings.data_plane_pool_size,
                max_overflow=settings.data_plane_max_overflow,
                connect_args=_asyncpg_connect_args(configuration),
            )
        except Exception as exc:  # malformed configuration, etc.
            raise DataPlaneUnavailable("connect_failed") from exc

        evicted = self._async_lru.put(cache_key, engine)
        if evicted is not None:
            await evicted.dispose()
        return engine

    # --- sync path (Celery workers) -----------------------------------------------

    def resolve_sync(self, tenant_id: str | None = None):
        if tenant_id is None:
            return self._platform_sync_engine()

        platform_engine = self._platform_sync_engine()
        with platform_engine.connect() as conn:
            record = get_data_plane_record_sync(tenant_id, conn)

            if record.is_platform:
                return self._platform_sync_engine()

            if record.status != "ready":
                raise DataPlaneNotReady(record.status)

            if not record.connection_id:
                raise DataPlaneUnavailable("connection_missing")

            row = self._fetch_connection_row(conn, record.connection_id)

        if row is None:
            raise DataPlaneUnavailable("connection_missing")

        cache_key = (tenant_id, record.connection_id, row.updated_at.isoformat() if row.updated_at else "")
        cached = self._sync_lru.get(cache_key)
        if cached is not None:
            return cached

        configuration = row.configuration or {}
        password = self._resolve_password(tenant_id, row.secret_references or {})
        try:
            engine = create_engine(
                _connection_url(configuration, password, async_driver=False),
                pool_size=settings.data_plane_pool_size,
                max_overflow=settings.data_plane_max_overflow,
                connect_args=_psycopg2_connect_args(configuration),
            )
        except Exception as exc:
            raise DataPlaneUnavailable("connect_failed") from exc

        evicted = self._sync_lru.put(cache_key, engine)
        if evicted is not None:
            evicted.dispose()
        return engine

    # --- invalidation --------------------------------------------------------------

    async def invalidate_tenant(self, tenant_id: str) -> None:
        """Dispose every cached engine for `tenant_id` in this process (Design D4 /
        routing spec scenario "Engine cache is invalidated on connection change"). Call
        alongside `src.shared.data_plane.invalidate` from the process that performs a
        pause, replace, or retire."""
        for engine in self._async_lru.pop_all_for_tenant(tenant_id):
            await engine.dispose()
        for engine in self._sync_lru.pop_all_for_tenant(tenant_id):
            engine.dispose()


_resolver = EngineResolver()


def set_engine_resolver(resolver: EngineResolver) -> None:
    """Replace the resolver. For tests."""
    global _resolver
    _resolver = resolver


def get_resolver() -> EngineResolver:
    return _resolver


def _retrying():
    return retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=settings.retry_initial_delay_seconds, max=settings.retry_max_delay_seconds),
        stop=stop_after_delay(settings.retry_max_total_seconds),
        reraise=True,
    )


def get_engine(tenant_id: str | None = None):
    """Synchronous accessor for the platform engine only (`tenant_id` is accepted for
    call-site compatibility but must be `None` or `platform`-mode — per-tenant
    resolution needs the control-plane lookup, which is async; use
    `await get_resolver().resolve(tenant_id)` or `get_resolver().resolve_sync(tenant_id)`
    for a `tenant_owned` tenant)."""
    if tenant_id is None:
        return _resolver._platform_engine()
    raise TypeError(
        "get_engine(tenant_id=...) cannot resolve a per-tenant engine synchronously; "
        "use `await get_resolver().resolve(tenant_id)` (async contexts) or "
        "`get_resolver().resolve_sync(tenant_id)` (Celery workers)"
    )


@_retrying()
async def wait_for_database() -> None:
    """Retry the first connection attempt with bounded exponential backoff so the
    service tolerates Postgres starting later than the service process itself."""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def get_session() -> AsyncSession:
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        yield session
