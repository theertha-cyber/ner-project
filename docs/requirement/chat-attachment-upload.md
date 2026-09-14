# Chat Attachment Upload — End-to-End Discovery and Requirements Baseline

## Document Control
| Field | Value |
| --- | --- |
| Title | Chat Attachment Upload |
| Version | 1.0 |
| Status | Draft baseline |
| Date | 2026-09-10 |
| Prepared from | User request in run `chat-attachment-upload-20260910`; clarified answers in conversation; `PROJECT.md`; `src/portal/src/components/chat/ChatInput.tsx`; `src/portal/src/app/(auth)/chat/page.tsx`; `src/portal/src/components/documents/DocumentUpload.tsx`; `src/portal/src/app/(auth)/documents/page.tsx`; codebase discovery report for chat and attachment behavior |
| Owner | Product / analysis |
| Approver | User |

### Run Configuration Answers
| Answer | Value | Status | Source |
| --- | --- | --- | --- |
| Target | analysis | confirmed | Run request |

No other run-configuration answers were stated in the source.

## Executive Summary
Chat input is currently text-only, while document upload already exists as a separate tenant-wide workflow. The requested change adds a chat attachment button in `ChatInput.tsx`, keeps retrieval conversation-scoped, allows the same ingestion file types plus CSV, and explicitly preserves the tenant-wide Documents tab/library behavior.

The user clarified that no sensitive/regulated data is expected, the user is the approver/sign-off authority, there is no hard deadline/budget/rollout constraint, conversation deletion must hard-delete uploaded files and derived artefacts, and the first attachment should not reserve a conversation until the user sends a message. **Readiness: Ready for Architecture.**

## Business Context and Success Measures
- **Need** — enable chat attachment upload from the chat composer so users can send supporting files in conversation. Status: Confirmed.
- **Outcome** — attachments are visible and retrievable only inside the conversation they belong to. Status: Confirmed.
- **Constraint** — tenant-wide Documents tab/library behavior must remain unchanged. Status: Confirmed.
- **Constraint** — no sensitive or regulated data is expected in scope. Status: Confirmed.
- **Constraint** — no hard deadline, budget cap, or rollout constraint was provided. Status: Confirmed.
- **Success measure** — users can attach files from `ChatInput.tsx`, and the conversation view reflects those attachments without affecting the Documents library. Status: Confirmed.

## Stakeholders, Users, Roles and Personas
- **Primary user** — chat user who uploads attachments in a conversation. Status: Confirmed.
- **Approver / sign-off authority** — user. Status: Confirmed.
- **Secondary impacted users** — existing Documents tab/library users who must see no behavior change. Status: Confirmed.

## Scope
### In Scope
- Chat attachment button in `ChatInput.tsx`. Status: Confirmed.
- Same ingestion file types as current upload flow, plus CSV. Status: Confirmed.
- Conversation-scoped visibility and retrieval for uploaded attachments. Status: Confirmed.
- Conversation reservation only when the user sends a message, not merely when an attachment is staged. Status: Confirmed.
- Hard-delete uploaded files and derived artefacts on conversation deletion. Status: Confirmed.

### Out of Scope
- Any change to tenant-wide Documents tab/library behavior. Status: Confirmed.
- Resume-specific or JD-specific modeling. Status: Confirmed.
- Introducing sensitive/regulated-data handling workflows. Status: Confirmed.

### Future Scope
- None identified. Status: Not Applicable.

## Current State
- `ChatInput.tsx` is text-only today; it renders a textarea and send button only, with no file input or attach control. Evidence: `src/portal/src/components/chat/ChatInput.tsx:16-123`. Status: Confirmed.
- Chat conversation state is already conversation-scoped in the page flow; messages are fetched by conversation ID, and a first message can create/adopt a conversation after send. Evidence: `src/portal/src/app/(auth)/chat/page.tsx:81-121`, `:129-157`, `:198-314`. Status: Confirmed.
- File upload already exists as a separate Documents-page flow, with tenant-wide library behavior and caller-fixed upload purpose. Evidence: `src/portal/src/app/(auth)/documents/page.tsx:61-128`, `src/portal/src/components/documents/DocumentUpload.tsx:18-291`. Status: Confirmed.

## User Journeys and Business Workflows
- User opens chat and adds an attachment from the composer before sending a message. Status: Confirmed.
- User sends the message, which may reserve/create the conversation if it does not yet exist. Status: Confirmed.
- User later reopens the same conversation and can retrieve the attachments only within that conversation. Status: Confirmed.
- User deletes the conversation and all uploaded files plus derived artefacts are hard-deleted. Status: Confirmed.

## Functional Requirements
| ID | Requirement | Source | Stakeholder | Journey | Acceptance Criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| FR-001 | Add a chat attachment button to `ChatInput.tsx`. | User request | Chat user | Compose message | Attachment affordance is present in the chat composer. | Confirmed |
| FR-002 | Support the same ingestion file types as the current upload flow, plus CSV. | User request | Chat user / platform | Attach file | Files accepted by chat include current supported types and CSV. | Confirmed |
| FR-003 | Keep attachment visibility and retrieval scoped to the conversation. | User request | Chat user | Open conversation | Attachments are retrievable only in the conversation where they were uploaded. | Confirmed |
| FR-004 | Do not change tenant-wide Documents tab/library behavior. | User request | Existing Documents users | Use library | Existing Documents UI/behavior remains unchanged. | Confirmed |
| FR-005 | Do not introduce resume-specific or JD-specific modeling. | User request | Chat user / data model | Attach file | Attachments are not forced into resume/JD entity modeling. | Confirmed |
| FR-006 | Reserve/create the conversation only when the user sends a message, not when the first attachment is staged. | User clarification | Chat user | First attachment / first send | No conversation is reserved solely by opening composer or staging an attachment. | Confirmed |
| FR-007 | Hard-delete uploaded files and derived artefacts on conversation deletion. | User clarification | Chat user / ops | Delete conversation | Deleted conversation content is not recoverable through the product UI. | Confirmed |
| FR-008 | No sensitive or regulated data is expected in scope. | User clarification | Product / security | Use feature | Feature baseline does not require regulated-data handling flows. | Confirmed |

## Reference Scenarios
| ID | Actors | Trigger / Input | Expected Observable Outcome | Source |
| --- | --- | --- | --- | --- |
| RS-001 | None found in source | N/A | N/A | No worked example was provided in the source requirement or clarifications. |

## Business Rules
| ID | Rule | Source | Status |
| --- | --- | --- | --- |
| BR-001 | Chat attachments originate from the chat composer, not the tenant Documents tab. | User request + current state | Confirmed |
| BR-002 | Conversation scoping governs visibility and retrieval. | User request | Confirmed |
| BR-003 | Conversation reservation waits until the user sends a message. | User clarification | Confirmed |
| BR-004 | Conversation deletion triggers hard-delete of uploaded files and derived artefacts. | User clarification | Confirmed |
| BR-005 | CSV is included in the allowed ingestion set. | User request | Confirmed |
| BR-006 | Resume/JD-specific modeling is excluded. | User request | Confirmed |
| BR-007 | Tenant-wide Documents behavior remains unchanged. | User request | Confirmed |

## Data Requirements
- **Attachment payloads** — store uploaded files associated with a chat conversation; retrieval must respect conversation scope. Status: Confirmed.
- **Derived artefacts** — any extracted or generated by-products tied to attachments must be deleted with the conversation. Status: Confirmed.
- **File classification** — no sensitive/regulated data is expected, so the feature baseline does not require regulated-data workflows. Status: Confirmed.
- **Content modeling** — attachments are not required to map to resume/JD-specific schemas. Status: Confirmed.

## Integration Requirements
- **Chat composer to chat backend** — attachment flow must fit the existing chat journey and conversation lifecycle. Status: Confirmed.
- **Upload pipeline** — the attachment flow must reuse the platform’s existing ingestion capability for the same file types plus CSV. Status: Confirmed.
- **Documents library isolation** — the separate tenant-wide Documents tab/library must not change as a side effect. Status: Confirmed.

## UI/UX and Accessibility Requirements
- **Composer affordance** — the chat composer must surface an attachment control in the same UI surface as the message box. Status: Confirmed.
- **Channel consistency** — attachment upload remains part of chat, not a separate Documents-library interaction. Status: Confirmed.
- **Accessibility** — the attachment control must be operable from keyboard and exposed with an accessible name. Status: Recommended.

## Security, Privacy and Compliance Requirements
| ID | Requirement | Driver (regulation / policy / risk) | Evidence Needed | Status |
| --- | --- | --- | --- | --- |
| SEC-001 | No sensitive or regulated data is expected in scope. | User clarification / scope boundary | User confirmation and acceptance baseline | Confirmed |
| SEC-002 | Conversation deletion must hard-delete uploaded files and derived artefacts. | Privacy / data minimization | Delete-path test evidence and storage cleanup evidence | Confirmed |
| SEC-003 | Tenant-wide Documents behavior must remain isolated from chat attachments. | Data segregation / blast-radius control | Regression evidence on Documents page | Confirmed |

## Non-Functional Requirements
| ID | Metric | Target | Measurement Point | Workload / Condition | Validation Method | Environment | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NFR-SEC-001 | Data classification coverage | No regulated-data handling workflow is introduced by this feature | Requirements baseline and acceptance review | Feature scope only | Review against approved scope | Analysis / staging | Product + Security | Confirmed |
| NFR-OPS-001 | Deletion completeness | Uploaded files and derived artefacts are not retrievable after conversation deletion | Post-delete retrieval surface | Deletion request | Automated delete/retrieve regression test | Staging | QA + Ops | Confirmed |
| NFR-UX-001 | Keyboard accessibility | Attachment control reachable and usable by keyboard | Chat composer UI | Normal browser use | Accessibility test / manual keyboard check | Staging | UX + QA | Recommended |

## Architecture-Driving Requirements and Constraints
The architecture must keep chat attachments separate from the tenant-wide Documents library while still reusing the existing ingestion capabilities where appropriate. It must preserve conversation-scoped retrieval, support CSV in the accepted set, and ensure hard-delete semantics for uploaded files and derived artefacts. The current chat lifecycle already allows conversation adoption after first send, so the new requirement is that attachment staging must not force earlier reservation.

## Technology Constraints, Preferences and Open Selections
| Area | Item | Tech Status | Driver / Rationale | Decision Owner |
| --- | --- | --- | --- | --- |
| Frontend | `ChatInput.tsx` in the React/Next.js portal is the mandated UI entry point. | Existing constraint | Requirement names the file and current app stack already uses it. | Architect |
| Frontend | Attachment control should follow existing portal patterns and styling. | Existing constraint | Maintain UI consistency and avoid changing the Documents page. | UX |
| Backend | Existing chat conversation API remains the integration anchor. | Existing constraint | Current chat page already uses conversation-scoped endpoints. | Architect |
| Data stores | Existing platform stores for conversation metadata and attachment artefacts are retained. | Existing constraint | Do not introduce a new tenant-wide library behavior. | Data |
| Integration | CSV handling within the ingestion flow is an open implementation choice. | Open for architecture decision | New file type is added to the accepted set. | Architect / Data |
| Infrastructure | Existing project infrastructure standards apply; no special rollout constraint was stated. | Existing constraint | User explicitly gave no deadline/budget/rollout constraint. | DevOps |

## Environment and Infrastructure Requirements
- **Target environment shape** — use the existing portal and backend environments already described in `PROJECT.md`. Status: Confirmed.
- **Deployment constraint** — no special rollout window or budget gate was supplied. Status: Confirmed.
- **Storage lifecycle** — infrastructure must support hard-delete of attachments and derived artefacts. Status: Confirmed.

## Engineering and Quality Requirements
- **Regression protection** — add coverage for composer attachment affordance, CSV acceptance, conversation-scoped retrieval, and hard-delete cleanup. Status: Confirmed.
- **Behavioral isolation** — keep Documents tab/library behavior unchanged. Status: Confirmed.
- **Coding/testing conventions** — follow the project’s React/TypeScript test conventions and existing portal patterns. Status: Mandated.

## Testing and Acceptance Strategy
- **Acceptance authority** — the user is the sign-off authority. Status: Confirmed.
- **Required test levels** — UI regression, integration of upload/delete paths, and conversation-scoped retrieval checks. Status: Confirmed.
- **Evidence required** — tests must prove attachment control presence, CSV support, unchanged Documents behavior, and hard-delete cleanup. Status: Confirmed.

## Delivery, Release and Deployment Requirements
- **Release timing** — no hard deadline, budget, or rollout constraint was provided. Status: Confirmed.
- **Rollout shape** — no special phased rollout requirement was stated. Status: Confirmed.
- **Release gate** — user approval is the required sign-off. Status: Confirmed.

## Migration and Rollout Requirements
- **Legacy migration** — not applicable; this feature adds chat attachments without replacing an existing system. Status: Not Applicable.
- **Coexistence / cutover** — not applicable beyond preserving the existing Documents library. Status: Not Applicable.

## Operations and Support Requirements
- **Support ownership** — no separate operational owner was supplied. Status: Open – Non-blocking.
- **Retention / cleanup** — hard-delete semantics are required for conversation deletion. Status: Confirmed.
- **Monitoring** — no feature-specific monitoring target was supplied; inherit existing platform observability. Status: Open – Non-blocking.

## Traceability Matrix
| Requirement ID | Source | Stakeholder / Owner | Acceptance Criterion | Validation Method | Status |
| --- | --- | --- | --- | --- | --- |
| FR-001 | User request | Chat user | Attachment control exists in composer | UI test / manual check | Confirmed |
| FR-002 | User request | Chat user / platform | CSV accepted with existing file types | Integration test | Confirmed |
| FR-003 | User request | Chat user | Retrieval is conversation-scoped | Conversation fetch test | Confirmed |
| FR-004 | User request | Existing Documents users | Documents page behavior unchanged | Regression test | Confirmed |
| FR-006 | User clarification | Chat user | Reservation waits until send | Chat lifecycle test | Confirmed |
| FR-007 | User clarification | Chat user / ops | Delete removes files and derived artefacts | Delete-path test | Confirmed |

## Decision Register
| ID | Decision Required | Context and Constraints | Options | Recommendation | Owner | Decision Deadline | Status | Downstream Impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEC-001 | How CSV is handled inside the attachment ingestion flow | CSV is newly added to the accepted set; existing ingestion already exists for other file types | Reuse current ingestion path; add CSV parser branch; defer CSV to document pipeline | Reuse existing ingestion path and add CSV support in the same contract boundary | Architect / Data | None stated | Open – Non-blocking | Data, Developer, QA |
| DEC-002 | Whether attachment staging can create any server-side placeholder before first send | User wants reservation only on send; current chat can adopt a conversation after first send | No placeholder until send; placeholder without reservation; immediate reservation on file attach | No placeholder until send | Architect | None stated | Confirmed | Architecture, Developer, QA |
| DEC-003 | Hard-delete coverage for derived artefacts | User requires hard-delete of uploaded files and derived artefacts | Delete only source file; delete source + generated artefacts; retain metadata only | Delete source + generated artefacts and remove user-visible retrieval | User / Architect | None stated | Confirmed | Data, Security, Ops, QA |

## Assumption Register
| ID | Assumption | Reason | Validation Owner | Validation Deadline | Impact if Incorrect |
| --- | --- | --- | --- | --- | --- |
| ASM-001 | Existing chat and upload infrastructure can be extended without tenant-wide Documents changes. | Current codebase already separates chat and Documents flows. | Architect | Before design complete | Scope expansion |

## Dependency Register
| ID | Dependency | Type | Owner | Needed By | Status | Impact if Unavailable |
| --- | --- | --- | --- | --- | --- | --- |
| DEP-001 | Existing chat conversation endpoints | Internal API | Backend | Design / implementation | Confirmed | Chat attachment flow cannot be wired in cleanly |
| DEP-002 | Existing Documents upload behavior | Internal UI / workflow | Portal | Design / regression | Confirmed | Risk of unintended library changes |
| DEP-003 | File-ingestion path that already supports current file types | Internal service capability | Platform | Design | Confirmed | CSV extension cannot be scoped cleanly |

## Risk Register
| ID | Risk | Likelihood | Impact | Mitigation | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- |
| RISK-001 | CSV support may diverge from existing ingestion assumptions. | Medium | Medium | Treat CSV as an explicit extension point and regression-test it. | Architect / Data | Open |
| RISK-002 | Conversation deletion may leave orphaned derived artefacts if cleanup is incomplete. | Medium | High | Require delete-path tests against source and derived artefact stores. | QA / Ops | Confirmed |
| RISK-003 | Changes may accidentally affect tenant-wide Documents behavior. | Medium | High | Keep chat attachment scope separate and add Documents-page regression coverage. | Developer / QA | Confirmed |

## Open Questions
### Blocking
None.

### Non-blocking
- **Support owner** — not named; owned by Operations at implementation time. Target stage: Operations. Status: Open – Non-blocking.
- **Monitoring detail** — no feature-specific observability target was provided; inherit platform defaults. Target stage: DevOps / Operations. Status: Open – Non-blocking.

## Readiness Assessment
**Overall rating: Ready for Architecture.** The core scope, preservation constraints, sign-off authority, data posture, and deletion requirement are now clear, and the current codebase evidence shows where the change fits.

| Workstream | Ready / Conditional / Blocked | Evidence | Remaining gap | Owner |
| --- | --- | --- | --- | --- |
| Product and business | Ready | Scope and exclusions are explicit. | None. | User / Product |
| UX | Ready | Chat composer is the touchpoint; a11y requirement recorded. | None. | UX |
| Architecture | Ready | Current chat and Documents flows are known; reservation timing clarified. | None. | Architect |
| Data | Ready | Conversation-scoped attachments and hard-delete requirement recorded. | CSV handling detail. | Data |
| Security | Ready | No sensitive/regulated data expected; deletion requirement clear. | None. | Security |
| Development | Ready | Existing chat composer and upload code paths are identified. | None. | Developer |
| QA | Ready | Acceptance criteria and delete/retrieve checks are traceable. | None. | QA |
| Infrastructure and DevOps | Ready | No special rollout constraint; existing platform assumed. | Support owner and monitoring detail. | DevOps |
| Migration | Ready | No legacy replacement or cutover. | None. | N/A |
| Operations | Conditional | Deletion/support expectations are known, but ownership is not named. | Operational owner and monitoring specifics. | Operations |

## Delivery Workstreams and Todo List
- **Business analysis** — confirm the baseline, exclusions, and user acceptance. Status: Confirmed.
- **UX** — map the composer attachment affordance into existing chat patterns. Status: Confirmed.
- **Architecture** — define the conversation-scoped attachment lifecycle and CSV extension boundary. Status: Confirmed.
- **Security** — validate the no-sensitive-data scope and hard-delete expectation. Status: Confirmed.
- **Data** — align attachment and derived-artefact storage/retrieval semantics. Status: Confirmed.
- **Development** — implement the composer affordance and regression-safeguarded flow. Status: Confirmed.
- **Testing** — cover CSV acceptance, conversation scoping, Documents isolation, and hard-delete cleanup. Status: Confirmed.
- **DevOps** — use existing environments and observability defaults. Status: Confirmed.
- **Migration** — not applicable. Status: Not Applicable.
- **Operations** — own support detail and monitoring follow-up. Status: Open – Non-blocking.

## Handoff Contract
- **Product / BA** — functional baseline, workflows, rules, scope, acceptance criteria.
- **UX** — composer journey, accessibility constraint, experience boundaries.
- **Architect** — attachment lifecycle, conversation reservation timing, CSV boundary, deletion semantics.
- **Security** — no regulated-data scope, deletion expectations, isolation from Documents library.
- **Developer** — confirmed behavior, current-state references, and regression targets.
- **QA** — traceable acceptance criteria for attachment button, CSV, scoping, and hard-delete.
- **DevOps** — existing environments, no special rollout constraint, observability inheritance.
- **Operations** — support expectations, deletion impact, and ownership follow-up.
