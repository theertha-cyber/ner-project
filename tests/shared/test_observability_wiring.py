"""Structural guards: one logging configuration, one request-identifier generator.

Verification rows 2 and 10.

Both are the same defect in two places. Eight `middleware/tenant_context.py` files each
grew their own `X-Request-ID` generator because each was written from the one next to it,
and because nobody owned the whole path, none of them forwarded the value onward — so an
identifier did not survive a single hop. Logging went the other way: only two processes
ever configured it, so the other eight discarded everything they logged.

These tests fail the moment either pattern reappears, which is the only thing that stops
the ninth copy.
"""

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.verification]

SRC = Path(__file__).resolve().parents[2] / "src"
OBSERVABILITY = SRC / "shared" / "observability"

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


def _python_sources():
    for path in SRC.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


class TestOnlyTheSharedModuleConfiguresLogging:
    """Row 2 — `logging.basicConfig` appears only under `src/shared/observability/`."""

    def test_basic_config_appears_nowhere_else(self):
        offenders = [
            path.relative_to(SRC).as_posix()
            for path in _python_sources()
            if OBSERVABILITY not in path.parents
            and "logging.basicConfig(" in path.read_text(encoding="utf-8")
        ]

        assert offenders == [], (
            "a second logging configuration makes the effective level depend on import "
            f"order: {offenders}"
        )

    def test_the_shared_module_does_configure_it(self):
        """The counterpart assertion — a passing test above means nothing if the shared
        module stopped configuring logging at all."""
        sources = "\n".join(
            path.read_text(encoding="utf-8") for path in OBSERVABILITY.rglob("*.py")
        )
        assert "logging.basicConfig(" in sources


class TestNoServiceGeneratesItsOwnRequestIdentifier:
    """Row 10 — the eight `tenant_context.py` files no longer mint identifiers."""

    # `uuid4()` assigned to anything request-identifier shaped, or a direct read of the
    # header with a generated fallback — the exact line each of the eight carried.
    _GENERATION = re.compile(r"uuid\.uuid4\(\)|uuid4\(\)")

    @pytest.mark.parametrize("service", SERVICES)
    def test_tenant_context_middleware_mints_no_identifier(self, service):
        path = SRC / service / "middleware" / "tenant_context.py"
        assert path.exists(), f"{service} has no tenant_context.py — did it move?"

        source = path.read_text(encoding="utf-8")
        assert not self._GENERATION.search(source), (
            f"{service} still generates a request identifier. Correlation has one "
            "implementation, in src/shared/observability/middleware.py."
        )

    @pytest.mark.parametrize("service", SERVICES)
    def test_tenant_context_middleware_keeps_its_security_concerns(self, service):
        """The consolidation removes the correlation block and nothing else. Token
        decoding and the exempt-path list are the platform's core access control under
        ADR-001 and stay per-service."""
        source = (SRC / service / "middleware" / "tenant_context.py").read_text(encoding="utf-8")

        assert "decode_token" in source or "widget_api_keys" in source
        assert "Authorization" in source

    def test_the_shared_middleware_is_the_only_generator(self):
        source = (OBSERVABILITY / "middleware.py").read_text(encoding="utf-8")
        assert "uuid.uuid4()" in source


class TestNoPrintInTheRequestAndWorkerPaths:
    """`print` is the one output path no logging control can reach.

    Not a style rule. `src/extraction_service/worker.py` printed
    `text_preview=<80 chars of the document>` straight to stdout — past the redaction
    filter, past the formatter, past the level, into `docker logs` — and the audit that
    grepped for `logger.` calls did not see it. The one-shot CLI scripts (`seed.py`,
    `verify_schema.py`, `ensure_mlflow_db.py`) legitimately print to a terminal and are
    not request-path telemetry, so they are out of scope here.
    """

    PATHS = (
        "extraction_service/worker.py",
        "chat_api/services/sql_generator.py",
        "chat_api/graph/nodes.py",
        "extraction_service/services/entity_postprocessor.py",
    )

    @pytest.mark.parametrize("relative", PATHS)
    def test_the_module_emits_through_logging(self, relative):
        source = (SRC / relative).read_text(encoding="utf-8")

        offenders = [
            line.strip()
            for line in source.splitlines()
            if line.lstrip().startswith("print(") or "traceback.print_exc()" in line
        ]
        assert offenders == [], (
            f"{relative} writes to stdout directly, where no filter can redact it: "
            f"{offenders[:2]}"
        )

    def test_the_document_text_preview_is_gone(self):
        source = (SRC / "extraction_service" / "worker.py").read_text(encoding="utf-8")

        assert "text_preview" not in source
        assert "doc_text_preview" not in source


class TestEveryServiceInitialisesObservability:
    """Every one of the eight entry points makes the single wiring call."""

    @pytest.mark.parametrize("service", SERVICES)
    def test_main_calls_init_observability(self, service):
        source = (SRC / service / "main.py").read_text(encoding="utf-8")
        assert f'init_observability("{service}"' in source

    @pytest.mark.parametrize(
        "module",
        ("training_service/celery_app.py", "extraction_service/celery_app.py"),
    )
    def test_each_worker_calls_init_observability(self, module):
        source = (SRC / module).read_text(encoding="utf-8")
        assert "init_observability(" in source
