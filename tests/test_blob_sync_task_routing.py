"""Blob sync Celery tasks route to the queue the blob_sync worker consumes.

Regression for DS-003 (`docs/bugs/tenant-self-service-data-sources.md`): beat
published `blob_sync_tick` to Celery's default `celery` queue, the general
worker discarded it as an unregistered task, and no scheduled sync ran. The
router is resolved exactly as `send_task` resolves it, so no broker is needed.
"""

import pytest

from src.document_service.blob_sync.tasks import (
    BLOB_SYNC_QUEUE,
    TASK_NAME,
    TICK_TASK_NAME,
    celery_app,
)


@pytest.mark.parametrize("task_name", [TASK_NAME, TICK_TASK_NAME])
def test_blob_sync_tasks_route_to_blob_sync_queue(task_name):
    route = celery_app.amqp.router.route({}, task_name)
    assert route["queue"].name == BLOB_SYNC_QUEUE == "blob_sync"


def test_beat_schedules_the_tick_task():
    entries = [e["task"] for e in celery_app.conf.beat_schedule.values()]
    assert TICK_TASK_NAME in entries
