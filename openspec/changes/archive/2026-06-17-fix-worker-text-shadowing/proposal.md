## Why

In `src/extraction_service/worker.py`, the local variable `text` (assigned from the HTTP response body) silently shadows the `text` import from SQLAlchemy. Every document processed in a batch run reaches the entity `INSERT` statement and raises `TypeError: 'str' object is not callable`, which is swallowed by the bare `except Exception` handler — incrementing `failed_count` and discarding all extracted entities. The run finishes with `status = 'completed'` and `failed_count = 1`, giving no indication that every extraction silently failed.

## What Changes

- Rename the local variable `text` in `worker.py` to `doc_text` everywhere it is assigned and read inside the processing loop
- No interface, schema, or API changes

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

_(none — existing `extraction-service` spec requirements are unchanged; this fix restores the behaviour those requirements already mandate)_

## Impact

- **`src/extraction_service/worker.py`**: single-file change, two assignment sites and one usage site (`text.split()`)
- No database schema changes, no API contract changes, no dependency changes

## Open Questions

_(none — root cause is confirmed, fix is unambiguous)_
