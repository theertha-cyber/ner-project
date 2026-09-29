"""Contract-validated SQL generation over uploaded files (tabular-file-chat spec).

The generator's LLM client is scripted; the validator, the Parquet cache, the
placeholder rewrite and the locked DuckDB executor are real."""

import pytest

from src.chat_api.services import tabular_executor
from src.chat_api.services import tabular_sql_generator as gen_module
from src.chat_api.services.external_sql_generator import EXTERNAL_SQL_SYSTEM_PROMPT
from src.chat_api.services.tabular_cache import ParquetCache
from src.chat_api.services.tabular_sql_generator import (
    TABULAR_OUTCOME_MESSAGES,
    TabularSQLGenerator,
)
from src.shared.tabular_files.capability import validation_contract
from tests.tabular_support import SALES_CONTRACT, SALES_ROWS_SQL, FakeObjectStore, ScriptedGeneratorClient, write_parquet

pytestmark = [pytest.mark.verification]

TENANT = "tenant-a"
FILE_ID = "11111111-1111-1111-1111-111111111111"
TARGETS_ID = "22222222-2222-2222-2222-222222222222"
STAFF_ID = "33333333-3333-3333-3333-333333333333"


def _served(file_id, contract, key):
    return {"file_id": file_id, "display_name": contract["source_file"], "version": 1, "sheet": None,
            "parquet_key": key, "contract": contract}


@pytest.fixture
def world(tmp_path, monkeypatch):
    objects = FakeObjectStore()
    sales_key = f"tenants/{TENANT}/tabular/{FILE_ID}/v1/data.parquet"
    write_parquet(tmp_path / "sales.parquet", SALES_ROWS_SQL)
    objects.put_file(sales_key, str(tmp_path / "sales.parquet"))
    targets_contract = {**SALES_CONTRACT, "relation": "targets", "source_file": "targets.csv",
                        "columns": [{"name": "region", "type": "text"}, {"name": "target", "type": "bigint"}]}
    staff_contract = {**SALES_CONTRACT, "relation": "staff", "source_file": "staff.csv",
                      "columns": [{"name": "name", "type": "text"}, {"name": "team", "type": "text"}]}
    files = [
        _served(FILE_ID, SALES_CONTRACT, sales_key),
        _served(TARGETS_ID, targets_contract, f"tenants/{TENANT}/tabular/{TARGETS_ID}/v1/data.parquet"),
        _served(STAFF_ID, staff_contract, f"tenants/{TENANT}/tabular/{STAFF_ID}/v1/data.parquet"),
    ]
    cache = ParquetCache(root=str(tmp_path / "cache"), max_bytes=10**9, object_store_factory=lambda: objects)
    generator = TabularSQLGenerator(cache=cache)

    async def resolve(tenant_id):
        assert tenant_id == TENANT
        return {"executable": True, "files": files}

    monkeypatch.setattr(generator, "_resolve", resolve)
    executed = []
    real_execute = tabular_executor.execute

    async def spy(tables, sql, params):
        executed.append((dict(tables), sql, dict(params)))
        return await real_execute(tables, sql, params)

    monkeypatch.setattr(tabular_executor, "execute", spy)

    class World:
        pass

    w = World()
    w.generator, w.executed, w.files = generator, executed, files
    return w


GOOD = {"sql": "SELECT SUM(amount) AS total FROM sales_q3 WHERE region = %(p1)s AND status = %(p2)s",
        "params": {"p1": "EMEA", "p2": "closed"}}


async def test_question_becomes_one_validated_select(world):
    """Scenario: Question becomes one validated SELECT."""
    world.generator.client = ScriptedGeneratorClient(GOOD)
    answer = await world.generator.answer("total closed revenue in EMEA?", TENANT)
    assert answer.reason is None
    assert answer.rows == [{"total": 1650}]
    assert answer.relations == ["sales_q3"]
    assert answer.columns == ["amount", "region", "status"]
    assert answer.files == [{"display_name": "sales_q3.csv", "version": 1, "sheet": None, "relation": "sales_q3"}]
    [(tables, sql, params)] = world.executed
    assert list(tables) == ["sales_q3"]  # only the referenced relation is loaded
    assert sql.count("SELECT") == 1 and "SUM(amount)" in sql
    assert params == {"p1": "EMEA", "p2": "closed"}
    assert "EMEA" not in sql and "closed" not in sql


async def test_prompt_reuses_fixed_rules_and_hides_excluded_columns(world):
    world.generator.client = ScriptedGeneratorClient(GOOD)
    await world.generator.answer("q", TENANT)
    messages = world.generator.client.requests[0]["messages"]
    assert messages[0]["content"] == EXTERNAL_SQL_SYSTEM_PROMPT
    assert "table sales_q3" in messages[1]["content"]
    assert "values of region: EMEA, APAC, AMER" in messages[1]["content"]
    assert "salary" not in messages[1]["content"]


async def test_excluded_column_cannot_be_queried(world):
    """Scenario: Excluded column cannot be queried (`salary` is not in the
    published `staff` contract)."""
    assert "salary" not in validation_contract(world.files)["relations"]["staff"]["columns"]
    world.generator.client = ScriptedGeneratorClient(
        {"sql": "SELECT salary FROM staff", "params": {}},
        {"sql": "SELECT salary FROM staff", "params": {}},
        {"sql": "SELECT salary FROM staff", "params": {}},
    )
    answer = await world.generator.answer("average salary?", TENANT)
    assert answer.reason == "generation_exhausted"
    assert world.executed == []
    feedback = world.generator.client.requests[1]["messages"][1]["content"]
    assert "unapproved_column (salary)" in feedback
    assert "SELECT" not in feedback.split("Question:")[1]


async def test_cross_file_query_is_rejected(world):
    """Scenario: Cross-file query is rejected."""
    cross = {"sql": "SELECT s.amount, t.target FROM sales_q3 s JOIN targets t ON s.region = t.region",
             "params": {}}
    world.generator.client = ScriptedGeneratorClient(cross, cross, cross)
    answer = await world.generator.answer("sales vs target?", TENANT)
    assert answer.reason == "generation_exhausted"
    assert world.executed == []
    assert "unapproved_join" in world.generator.client.requests[1]["messages"][1]["content"]


async def test_write_statement_never_executes(world):
    """Scenario: Write statement never executes."""
    drop = {"sql": "DROP TABLE sales_q3", "params": {}}
    world.generator.client = ScriptedGeneratorClient(drop, drop, drop)
    answer = await world.generator.answer("drop it", TENANT)
    assert answer.reason == "generation_exhausted"
    assert world.executed == []
    assert "write_or_ddl" in world.generator.client.requests[1]["messages"][1]["content"]


async def test_exhausted_generation_gives_a_fixed_message(world):
    """Scenario: Exhausted generation gives a fixed message — three rejected
    candidates (the first plus at most two retries), then a fixed outcome."""
    bad = {"sql": "SELECT * FROM secrets", "params": {}}
    world.generator.client = ScriptedGeneratorClient(bad, bad, bad, GOOD)
    answer = await world.generator.answer("q", TENANT)
    assert answer.reason == "generation_exhausted"
    assert len(world.generator.client.requests) == 3
    message = TABULAR_OUTCOME_MESSAGES[answer.reason]
    assert "SELECT" not in message and "secrets" not in message


async def test_retry_then_accept(world):
    world.generator.client = ScriptedGeneratorClient({"sql": "DELETE FROM sales_q3", "params": {}}, GOOD)
    answer = await world.generator.answer("q", TENANT)
    assert answer.rows == [{"total": 1650}]
    assert len(world.executed) == 1


async def test_no_ready_files_is_not_executable(world, monkeypatch):
    async def none(tenant_id):
        return {"executable": False, "reason": "not_executable"}

    monkeypatch.setattr(world.generator, "_resolve", none)
    world.generator.client = ScriptedGeneratorClient(GOOD)
    answer = await world.generator.answer("q", TENANT)
    assert answer.reason == "not_executable"
    assert world.generator.client.requests == []


def test_generator_client_is_not_traced():
    """ADR-016: the generator's client is a plain SDK client, never wrapped by
    a LangSmith tracer."""
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    generator = TabularSQLGenerator(cache=ParquetCache(root="unused"))
    assert type(generator.client) in (AsyncOpenAI, AsyncAzureOpenAI)
    assert "wrap_openai" not in open(gen_module.__file__, encoding="utf-8").read()
