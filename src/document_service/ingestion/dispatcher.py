"""Post-ingestion processing dispatch.

The payload is document identity and tenant identity, and nothing else. No bytes, no
storage reference, no media type — so a dispatch is replayable from persisted state
alone, which is the precondition for the queued dispatcher that bulk sync will need.
Anything carried here instead of persisted could not survive a restart or a queue.
"""

import asyncio
from typing import Protocol, runtime_checkable


@runtime_checkable
class ProcessingDispatcher(Protocol):
    def dispatch(self, document_id: str, tenant_id: str) -> None: ...


class InProcessDispatcher:
    """Today's behaviour, unchanged: an `asyncio` task in the API process."""

    def dispatch(self, document_id: str, tenant_id: str) -> None:
        # Imported at call time: the worker imports the content store, which imports
        # configuration, and a module-level import here would close the loop.
        from src.document_service.services.ocr_worker import process_document

        asyncio.create_task(process_document(document_id, tenant_id))


class RecordingDispatcher:
    """Records dispatches without executing them. For tests and for verification row 20."""

    def __init__(self):
        self.dispatches: list[tuple[str, str]] = []

    def dispatch(self, document_id: str, tenant_id: str) -> None:
        self.dispatches.append((document_id, tenant_id))
