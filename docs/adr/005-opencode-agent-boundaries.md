# ADR-005: OpenCode Agent Permissions and Boundaries

**Status**: Proposed

**Date**: 2026-06-04

## Context

OpenCode agents perform planning, coding, review, QA, security, and MLOps tasks. Agents must be bounded to prevent unintended actions (e.g., a coding agent modifying infrastructure config, a QA agent deploying to production). Requirements mandate "bounded agents for planning, coding, review, QA, security, and MLOps tasks."

We evaluated three models:

- **(a) Single general-purpose agent**: All capabilities in one agent. Simple to manage but high risk of unintended cross-domain actions.
- **(b) Role-specific agents with bounded tool access**: Each agent has a defined scope, allowed tools, and forbidden actions. Human retains approval authority at gates.
- **(c) Fully automated agent pipeline**: Agents operate autonomously with human only at end gates. Fastest but highest risk.

## Decision

**Use role-specific agents with bounded tool access** (strategy b), with human approval gates at key decision points.

| Agent Role | Allowed Actions | Forbidden Actions | Approval Required |
|---|---|---|---|
| Planner | Read requirements/specs, write proposals/design docs | Write implementation code | — |
| Developer (Backend/Frontend/MLOps) | Read specs, write implementation code in domain | Modify specs, approve changes, deploy to production | PR approval |
| Reviewer (BA/Architect/QA/Developer) | Read-only access to change artifacts, produce review reports | Write implementation code, modify artifacts | — |
| Security Agent | Read code/config, produce security reports, block changes | Modify code, approve changes | Escalation on violations |
| Documentation Agent | Read code, write docs | Modify source code | — |

All agents operate within context defined by AGENTS.md and task-specific instructions. Agent definitions reside in `.opencode/agents/` — one file per role.

## Consequences

### Positive
- Clear separation of concerns prevents accidental cross-domain changes.
- Reviewer agents serve as independent quality gates.
- Human retains final approval authority at each gate.
- Agent execution logs provide audit trail.

### Negative
- Multiple agent handoffs increase end-to-end time for simple changes.
- Agent boundary definitions must be kept in sync with project conventions.
- Overly restrictive boundaries may block legitimate cross-domain changes.

### Mitigations
- Cross-domain changes split into per-domain tasks with shared specs.
- Coordination agent (Planner) orchestrates multi-agent workflows.
- Human override available for legitimate cross-domain changes.

## Compliance

- Agent definitions reside in `.opencode/agents/` — one file per role.
- Each agent definition MUST list allowed tools, forbidden actions, and required approval gates.
- Agent execution logs are stored for audit.
- Violations (agent performing out-of-bound actions) trigger escalation to human.

## References

- Requirements §FR-14 (OpenCode-assisted engineering with bounded agents)
- Technical Design Document §4.4 (Technology choices)
