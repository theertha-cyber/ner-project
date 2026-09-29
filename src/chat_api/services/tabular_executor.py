"""Locked in-memory DuckDB execution for uploaded tabular files (ADR-018).

Per accepted statement (design.md Decision 5):
1. a fresh `:memory:` connection with `memory_limit` and `threads` set;
2. `CREATE TABLE <relation> AS SELECT * FROM read_parquet(<cached path>)` for
   the relations the validator accepted — names from the served contract,
   paths from the cache manager, never from model output;
3. `SET enable_external_access=false; SET lock_configuration=true` — after
   loading, because disabling external access also blocks `read_parquet`;
4. `%(pN)s` placeholders rewritten to DuckDB's `$pN` on the already-validated
   text, and params bound by name, never interpolated;
5. a timer interrupts the statement at the timeout; at most max_rows + 1 rows
   are fetched to set the truncation flag;
6. the connection is closed.

Runs in a worker thread behind a per-worker semaphore. Every failure is one of
`execution_timeout`, `execution_failed` or `resource_limit`.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import decimal
import logging
import re
import threading

import duckdb

from src.shared.config import settings
from src.shared.tabular_files.identifiers import IDENTIFIER_RE

logger = logging.getLogger(__name__)

REASON_TIMEOUT = "execution_timeout"
REASON_FAILED = "execution_failed"
REASON_RESOURCE = "resource_limit"

_PLACEHOLDER_RE = re.compile(r"%\(([A-Za-z_][A-Za-z0-9_]*)\)s")

_semaphores: dict[int, asyncio.Semaphore] = {}


class TabularExecutionFailed(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def rewrite_placeholders(sql: str) -> tuple[str, list[str]]:
    """`%(p1)s` to `$p1` on validated text only; returns the names used."""
    names: list[str] = []

    def _sub(match):
        names.append(match.group(1))
        return f"${match.group(1)}"

    return _PLACEHOLDER_RE.sub(_sub, sql), names


def _jsonable(value):
    if isinstance(value, decimal.Decimal):
        normalized = value.normalize()
        return int(normalized) if normalized == normalized.to_integral_value() else float(normalized)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    return value


def execute_locked(tables: dict[str, str], sql: str, params: dict, *, memory_limit: str | None = None,
                   threads: int | None = None, timeout: float | None = None,
                   max_rows: int | None = None) -> tuple[list[dict], bool]:
    """Blocking execution; `tables` maps relation name to local Parquet path."""
    memory_limit = memory_limit or settings.tabular_exec_memory_limit
    threads = threads or settings.tabular_exec_threads
    timeout = timeout if timeout is not None else settings.tabular_exec_timeout_seconds
    max_rows = max_rows or settings.tabular_exec_max_rows

    con = duckdb.connect(":memory:", config={"memory_limit": memory_limit, "threads": threads})
    timer = None
    try:
        for relation, path in tables.items():
            if not IDENTIFIER_RE.match(relation):
                raise TabularExecutionFailed(REASON_FAILED)
            con.execute(f"CREATE TABLE {relation} AS SELECT * FROM read_parquet(?)", [path])
        con.execute("SET enable_external_access=false")
        con.execute("SET lock_configuration=true")

        statement, names = rewrite_placeholders(sql)
        bound = {name: params[name] for name in dict.fromkeys(names)}
        timer = threading.Timer(timeout, con.interrupt)
        timer.start()
        cursor = con.execute(statement, bound)
        columns = [d[0] for d in cursor.description]
        fetched = cursor.fetchmany(max_rows + 1)
        timer.cancel()
        truncated = len(fetched) > max_rows
        rows = [{c: _jsonable(v) for c, v in zip(columns, row)} for row in fetched[:max_rows]]
        return rows, truncated
    except TabularExecutionFailed:
        raise
    except duckdb.InterruptException as exc:
        raise TabularExecutionFailed(REASON_TIMEOUT) from exc
    except duckdb.OutOfMemoryException as exc:
        raise TabularExecutionFailed(REASON_RESOURCE) from exc
    except (duckdb.Error, KeyError) as exc:
        logger.info("tabular_execution_failed", extra={"error_class": type(exc).__name__})
        raise TabularExecutionFailed(REASON_FAILED) from exc
    finally:
        if timer is not None:
            timer.cancel()
        con.close()


def _semaphore() -> asyncio.Semaphore:
    loop_id = id(asyncio.get_running_loop())
    semaphore = _semaphores.get(loop_id)
    if semaphore is None:
        semaphore = asyncio.Semaphore(max(1, settings.tabular_exec_concurrency))
        _semaphores[loop_id] = semaphore
    return semaphore


async def execute(tables: dict[str, str], sql: str, params: dict) -> tuple[list[dict], bool]:
    """Async entry point: bounded concurrency, execution off the event loop."""
    async with _semaphore():
        return await asyncio.to_thread(execute_locked, tables, sql, params)
