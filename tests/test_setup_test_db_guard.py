import os
import subprocess
import sys

import pytest

from src.shared.config import settings

_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "setup_test_db.py")


def _run_script(env_overrides: dict) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, _SCRIPT],
        cwd=os.path.dirname(_SCRIPT),
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.asyncio
class TestSetupTestDbGuard:
    async def test_refuses_dev_database(self):
        dev_url = "postgresql+asyncpg://ner:ner@localhost:5432/ner_dev"
        result = _run_script({"NER_DATABASE_URL": dev_url})

        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "ner_dev" in combined
        # No progress markers from main() means it exited at the guard, before
        # any DDL or DML ran.
        assert "Created public tables" not in combined
        assert "Created tables in schema" not in combined
        assert "Inserted test tenants" not in combined
        assert "Done." not in combined

    async def test_allows_test_database(self):
        result = _run_script({"NER_DATABASE_URL": settings.database_url})
        assert result.returncode == 0
        assert "Done." in result.stdout

    async def test_guard_reads_env_url_not_default(self):
        # The script's own hardcoded default already points at a database ending
        # in "_test" — this proves the guard evaluates NER_DATABASE_URL, not that
        # baked-in default, when it differs.
        non_test_url = "postgresql+asyncpg://ner:ner@localhost:5432/ner_dev"
        result = _run_script({"NER_DATABASE_URL": non_test_url})
        assert result.returncode != 0
        assert "ner_dev" in result.stdout + result.stderr

    async def test_override_permits_nonstandard_name(self):
        scratch_url = "postgresql+asyncpg://ner:ner@localhost:5432/ner_ci_scratch"
        result = _run_script({
            "NER_DATABASE_URL": scratch_url,
            "NER_ALLOW_NONSTANDARD_TEST_DB": "1",
        })
        combined = result.stdout + result.stderr
        assert "WARNING" in combined
        assert "ner_ci_scratch" in combined
        # It proceeds past the guard (fails later trying to connect to a
        # database that doesn't exist, which is expected — the guard itself
        # must not be what stops it).
        assert "Refusing to run" not in combined

    async def test_unset_override_keeps_guard(self):
        dev_url = "postgresql+asyncpg://ner:ner@localhost:5432/ner_dev"
        env = os.environ.copy()
        env.pop("NER_ALLOW_NONSTANDARD_TEST_DB", None)
        env["NER_DATABASE_URL"] = dev_url
        result = subprocess.run(
            [sys.executable, _SCRIPT],
            cwd=os.path.dirname(_SCRIPT),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "Refusing to run" in result.stdout + result.stderr
