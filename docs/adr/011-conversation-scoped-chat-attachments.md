# 011. Conversation-Scoped Chat Attachments in the Existing Document Model

## Status
Proposed

## Context
Chat attachments must stay invisible to the tenant-wide Documents library while still using the existing ingestion pipeline and supporting hard-delete on conversation removal. The current system already stores document content, spans, and chunks separately from chat conversations, and chat turns are already conversation-scoped.

## Decision
Store chat attachments as document rows with a nullable `conversation_id` that links each file to exactly one conversation, and treat those rows as conversation-owned content everywhere outside the chat thread.

Conversation deletion will hard-delete the linked document rows, their derived spans and chunks, and the underlying blob objects before the conversation row is removed.

## Alternatives Considered
| Option | Why not chosen |
| --- | --- |
| Separate attachment table plus separate file store records | Adds another join layer and duplicates lifecycle logic without improving isolation. |
| Soft-delete attachments and hide them in the UI | Violates the hard-delete requirement and leaves recoverable artefacts behind. |
| Put attachments in the existing Documents library with a flag only | Risks accidental tenant-wide exposure and makes preservation of current library behavior harder. |

## Consequences
Conversation scoping becomes a first-class persistence rule, and library queries must exclude conversation-linked documents explicitly. The design keeps the existing ingestion code reusable, but delete handling must now clean up storage and derived tables in the same request path.

## Related
- Requirement(s): FR-001, FR-003, FR-004, FR-006, FR-007
- Supersedes / Superseded by: None
