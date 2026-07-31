## REMOVED Requirements

### Requirement: Bounded agentic retrieval loop

**Reason**: Superseded by the Intent Orchestrator, which makes a single planning call and executes the resulting plan. The observe/re-plan cycle was the main source of per-turn latency and cost variance, and its behaviour was reachable only behind a feature flag.

**Migration**: `run_agentic_loop` and `src/chat_api/graph/agentic.py` are removed. Multi-operation retrieval is expressed as multiple entries in one orchestrator plan; see the `retrieval-orchestration` capability.

### Requirement: Iteration, tool-call, and wall-clock budgets

**Reason**: With no iteration cycle there is no iteration budget.

**Migration**: Replaced by the orchestrator's per-plan invocation cap and wall-clock deadline. `agentic_max_iterations`, `agentic_max_iterations_complex`, and `agentic_observation_char_limit` are removed from configuration; the tool-call cap and deadline settings are carried forward as the orchestrator's budgets.

### Requirement: Planner-signalled termination

**Reason**: A single planning call terminates by definition.

**Migration**: A planner response containing no capability selections is treated as an empty plan and triggers the orchestrator's degraded fallback.

### Requirement: Evidence accumulation into existing state keys

**Reason**: Restated for the orchestrator.

**Migration**: The same accumulation, dedupe, ranking, and error semantics are specified under `retrieval-orchestration`.

### Requirement: Tenant scope is unreachable from planner-supplied arguments

**Reason**: Restated for the orchestrator.

**Migration**: Specified under `retrieval-orchestration`; the guarantee is unchanged.

### Requirement: Tool observations are treated as evidence, not instructions

**Reason**: No retrieval result is ever returned to the planner, so retrieved content cannot influence planning at all. The requirement's protection is obtained structurally rather than by prompt instruction.

**Migration**: None. Retrieved content continues to reach the generation prompt only as context data.

### Requirement: Malformed tool calls get one corrective retry, then the loop degrades

**Reason**: A corrective retry requires a second planning call.

**Migration**: Invalid plan entries are discarded; if every entry is invalid, the orchestrator's degraded fallback runs both capabilities on the raw query.

### Requirement: Loop failure falls back to one-shot retrieval

**Reason**: There is no separate one-shot path to fall back to.

**Migration**: Replaced by the orchestrator's fallback plan — both capabilities on the raw user query, turn marked degraded.

### Requirement: Per-iteration loop trace

**Reason**: There are no iterations to index.

**Migration**: Replaced by the orchestrator plan trace, one entry per plan entry.

### Requirement: Feature flag and flag-off equivalence

**Reason**: The change removes runtime feature-flag routing entirely; there is one topology.

**Migration**: `chat_agentic_retrieval` and `chat_use_graph` are removed from settings. Deployments setting either environment variable must drop them; the graph pipeline is the only behaviour.

### Requirement: Loop is measured against the one-shot configuration

**Reason**: The comparison target no longer exists.

**Migration**: The eval harness measures the orchestrator plan-and-execute path against a direct `semantic_retrieval` baseline; see the `retrieval-eval` delta.
