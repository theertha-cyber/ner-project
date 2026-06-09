---
name: c4-diagram
description: Generates C4 architecture diagrams using the Structurizr MCP. Use when the user asks for C4 diagrams, architecture diagrams, system context, container diagrams, component diagrams, or deployment diagrams. Runs a structured discovery interview (cloud platform, architectural patterns), confirms decisions, then produces validated Structurizr DSL and exports to C4-PlantUML and Mermaid.
compatibility: Requires mcp__structurizr__* tools (structurizr MCP server).
metadata:
  generated_at: "2026-04-22"
  generator: "custom/c4-diagram"
---

# C4 Architecture Diagram Generator

## Trigger

Activate when the user asks for: "C4 diagram", "C4 model", "architecture
diagram", "system context", "container diagram", "component diagram",
"deployment diagram", "generate architecture", "document architecture".

---

## References (load on demand, per phase)

Keep these out of context until their phase:

| File | Load when |
|---|---|
| `references/cloud-platforms.md` | Phase 3b — after the user confirms a cloud platform; load only the section for the chosen platform. |
| `references/pattern-annotations.md` | Phase 3c — after patterns are confirmed; load only the sections for confirmed patterns. |
| `references/dsl-example.md` | Phase 4 — when authoring the DSL; use as structural reference, not copy-paste. |
| `references/sprite-mappings.md` | Phase 7 — only if PlantUML was selected in Phase 1 Q9. |

---

## C4 Levels

| Level | Audience | Focus |
|---|---|---|
| L1 — System Context | Everyone (exec → dev) | System + external actors |
| L2 — Container | Technical teams | Apps, DBs, services, cloud-managed services |
| L3 — Component | Developers | Internal components per container |

Default: generate **L1 + L2 + L3** unless the user specifies otherwise.
**L4 (Deployment) is not currently supported.** If requested, surface this
limitation and offer L1 + L2 + L3.

---

## Workflow

### Phase 1 — Architecture Discovery Interview

**MANDATORY.** Before writing any DSL, run this interview in a **single
message**. Wait for answers, then proceed to Phase 2.

> **Fast-path**: if the user has already described the system in detail in
> this conversation, skip to Phase 2 confirmation — do not re-ask.

Ask these questions, grouped as sections (exact prompts below):

**1. System Overview** — system name + one-sentence purpose; user types
(customers, employees, admins, partners).

**2. Architecture Style** — choose one: Monolithic / Modular Monolith /
Microservices / Event-driven / Serverless / Other.

**3. Tech Stack** — Frontend; Backend / API; Database(s); Cache / Queue;
Auth.

**4. Cloud & Infrastructure** — cloud vs. on-prem; if cloud, which
platform (AWS / Azure / GCP / Multi-cloud / On-prem); observability
infrastructure yes/no; networking topology (hub-spoke / zero-trust /
private endpoints only / none).

**5. Architectural Patterns in Use** — check all that apply: Saga
(Choreography), Saga (Orchestration), CQRS, Outbox, Circuit Breaker +
Retry, BFF, API Gateway, Event-driven / DLQ, Hub-Spoke, DDD, Other.

**6. External Integrations** — third-party APIs or internal systems; for
each: purpose + protocol.

**7. Key Components (for L3)** — pick 1–2 most important containers and
list their internal components.

**8. Diagram Levels** — default L1 + L2 + L3; which containers to break
down into L3.

**9. Output Formats** — select all: DSL only / Mermaid / PlantUML / All
three (default).

### Phase 2 — Architecture Confirmation

Produce a structured confirmation summary and ask the user to approve
before generating any DSL. Include:

- System name + one-line purpose.
- Architecture style + implication (e.g., "each microservice = separate
  Container with its own DB").
- Cloud platform + service mapping preview (e.g., "Message Queue → Azure
  Service Bus").
- Architectural patterns detected + how each appears in the diagram.
- Networking topology.
- Observability (included / excluded; list containers if included).
- Users / actors.
- L2 containers table (Container | Technology | Type | Tag).
- External systems table.
- L3 components list (per broken-down container; note patterns).
- Diagrams to generate + output formats.

Only proceed to Phase 3 after the user confirms.

### Phase 3 — Architecture Style Rules

Apply these before writing DSL:

- **Monolithic** — one Container for the app + one for the DB; L3 shows
  internal layers (Controllers / Services / Repositories). Do NOT split
  into separate microservice containers.
- **Modular Monolith** — one Container; each module its own component
  group in L3 (e.g., BookingModule, PaymentModule). Shared DB is one
  Container.
- **Microservices** — each service = one Container with tag `"Service"`;
  each DB-owning service gets its own `ContainerDb`; shared infra (API
  Gateway, Message Bus) = separate Containers. L3 breaks down one or two
  key services.
- **Event-driven** — message bus = Container tagged `"Queue"`; show
  producers → queue → consumers as relationships; L3 shows
  producers/consumers/handlers; add DLQ as a separate Queue Container
  when DLQ is confirmed.
- **Serverless** — Functions = Containers tagged `"Service"` with tech
  "AWS Lambda" / "Azure Function"; API Gateway = Container tagged
  `"Service"`; trigger sources appear as relationships.

### Phase 3b — Cloud Platform Service Mapping

Load `references/cloud-platforms.md` (only the section for the confirmed
platform). Replace every generic technology label in the DSL
`technology` field with the platform-specific managed service name.

### Phase 3c — Pattern Annotation

Load `references/pattern-annotations.md` (only the sections for confirmed
patterns). Apply its annotation rules to container/component descriptions
and relationship labels.

### Phase 4 — Author Structurizr DSL

Write the DSL based on confirmed answers. Load `references/dsl-example.md`
as a structural reference (not copy-paste). **Mandatory rules** (see
"DSL Rules" below). The `styles` block is mandatory.

### Phase 5 — Validate DSL

```
ToolSearch: select:mcp__structurizr__validate
mcp__structurizr__validate(dsl: "<full DSL string>")
```

If validation fails, fix and re-validate. **Cap: 3 fix attempts.** If
still failing, stop and surface the error. Common fixes:

- All IDs used in relationships must be declared first.
- Component IDs must reference the correct parent container.
- `component` view keyword must reference a container ID, not a software
  system ID.
- Duplicate relationships — if you declare `personA -> container` and
  also `personA -> system` (implicit), remove the outer one.
- Inline `{ tags }` on softwareSystem line — expand to flat third
  parameter or multi-line block.

### Phase 6 — Export (conditional on Phase 1 Q9)

- **DSL only**: skip export.
- **Mermaid** (or "All three"): load `mcp__structurizr__export-mermaid`
  and export every view key.
- **PlantUML** (or "All three"): load
  `mcp__structurizr__export-c4plantuml` and export every view key.

Example:

```
# Mermaid selected
export-mermaid(dsl, viewKey: "SystemContext")
export-mermaid(dsl, viewKey: "Containers")
export-mermaid(dsl, viewKey: "BookingComponents")   # repeat per L3 view
```

### Phase 7 — Enhance PlantUML with Icons

**Only if PlantUML was selected.** Load `references/sprite-mappings.md`
and apply it to every `.puml` file: sprite library headers,
`UpdateElementStyle` color overrides, technology → sprite inclusion, and
element macro selection.

### Phase 8 — Save Output

Always save `docs/architecture/workspace.dsl`.

Save `.puml` files only if PlantUML selected:

```
docs/architecture/
├── SystemContext.puml
├── Containers.puml
└── [Name]Components.puml      # one per broken-down container
```

Save `.mmd` files only if Mermaid selected:

```
docs/architecture/
├── SystemContext.mmd
├── Containers.mmd
└── [Name]Components.mmd
```

**Rendering:**

- `.dsl` → `docker run --rm -p 8888:8080 -v "<abs-path>/docs/architecture:/usr/local/structurizr" structurizr/structurizr local` → http://localhost:8888
- `.puml` → VS Code PlantUML extension (Alt+D) with server `https://www.plantuml.com/plantuml`
- `.mmd` → VS Code Markdown preview (Ctrl+Shift+V) with `bierner.markdown-mermaid`

---

## DSL Rules

- Every element: **name**, **description**, **technology** (containers /
  components).
- Unidirectional arrows only: `A -> B`.
- Relationships: action-verb label + protocol in quotes.
- Tags: `"Database"` → Cylinder, `"Queue"` → Pipe, `"Web Browser"` →
  WebBrowser, `"External System"` → grey, `"Observability"` → purple,
  `"Bounded Context"` → dashed border, `"Saga Participant"` (DDD /
  saga).
- **Never** use `theme default` — always explicit `styles` block.
- **Never** use `!identifiers hierarchical` — causes blank rendering in
  Structurizr Local.
- **Never** put `{ tags "..." }` inline on the same line as the
  description — the parser rejects with "Too many tokens". Expand to a
  multi-line block:

  ```
  myExt = softwareSystem "Name" "Description" {
      tags "External System"
  }
  ```

- Always validate DSL with MCP before saving.
- Use platform-specific managed service names in technology fields (see
  `references/cloud-platforms.md`).

---

## Audience Guide

| Stakeholder | Levels |
|---|---|
| Executives / PMs | L1 only |
| Tech leads / Architects | L1 + L2 |
| Developers | L1 + L2 + L3 |
| DevOps / Ops | L4 Deployment (not yet supported) |

---

## Error Handling

| Error | Fix |
|---|---|
| DSL validation fails | All IDs in relationships must be declared before use |
| `Too many tokens` on softwareSystem line | Inline `{ tags "..." }` not allowed — expand to multi-line block |
| Missing technology | Add tech string to all containers and components |
| `component` view fails | The view ID must reference a container, not a software system |
| Blank Structurizr render | Remove `!identifiers hierarchical`; use simple element IDs |
| Sprites not rendering | Ensure PlantUML server mode in VS Code settings |
| Colors not applying | Use `UpdateElementStyle()` — not `AddPersonTag()` / `AddSystemTag()` |
| MCP validator passes but Structurizr Local rejects | MCP parser is lenient; treat browser render as ground truth |
| Platform services not showing | Technology field must use exact managed-service name from `references/cloud-platforms.md` |
| Observability containers cluttering L2 | Move them to a separate `filtered` view if density is too high |
