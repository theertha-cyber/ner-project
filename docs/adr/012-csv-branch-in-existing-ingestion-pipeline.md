# 012. CSV Support as a Branch in the Existing Ingestion Pipeline

## Status
Proposed

## Context
The document service already has one ingestion path for supported files, and the extraction worker dispatches by media type. CSV is the only newly required file type, and the requirement is to preserve the existing ingestion path rather than introduce a separate CSV subsystem.

## Decision
Extend the current ingestion allow-list and extraction worker with a CSV branch that parses rows into normalized text spans, then flows through the same chunking, embedding, and retrieval pipeline used for query documents.

## Alternatives Considered
| Option | Why not chosen |
| --- | --- |
| Stand up a separate CSV ingestion service | Higher operational cost and unnecessary duplication for one file type. |
| Convert CSV to PDF or another intermediary format before ingesting | Adds avoidable transformation loss and complexity. |
| Reject CSV support for chat attachments | Fails the approved requirement baseline. |

## Consequences
CSV becomes a first-class supported input without changing the document architecture or adding a new storage type. The worker gains one more media-type branch, and parser tests must cover delimiter and row-shape edge cases.

## Related
- Requirement(s): FR-002
- Supersedes / Superseded by: None
