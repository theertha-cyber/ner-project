# C4 Architecture Diagrams — Corporate Travel Portal

## Prerequisites

| Tool | Purpose | Install |
|---|---|---|
| Docker Desktop | Runs Structurizr locally | [docker.com](https://www.docker.com/products/docker-desktop/) |
| VS Code (optional) | Edit `workspace.dsl` with syntax highlighting | [marketplace: Structurizr](https://marketplace.visualstudio.com/items?itemName=systemsarchitect.vscode-structurizr) |

## Render Diagrams

```bash
docker run -it --rm -p 8080:8080 \
  -v "$(pwd):/usr/local/structurizr" \
  structurizr/structurizr local
```

Open **http://localhost:8080** — diagrams update live as you save `workspace.dsl`.

## Views

| View Key | Level | Description |
|---|---|---|
| `SystemContext` | L1 | System + actors + external systems |
| `Containers` | L2 | All microservices, DBs, queues, observability |
| `BookingComponents` | L3 | Booking Service internals (Saga, CQRS, Outbox) |
| `PolicyComponents` | L3 | Policy Service internals (budget rule enforcement) |

## Using Claude Code to Generate / Validate DSL (c4-diagram skill)

The `c4-diagram` skill in Claude Code uses the **Structurizr MCP server** to validate DSL and export diagrams. This is separate from the viewer above.

### Step 1 — Run the MCP server

```bash
docker run -it --rm -p 3000:3000 -e PORT=3000 structurizr/mcp -dsl -plantuml -mermaid
```

Keep this running while you use the skill in Claude Code.

### Step 2 — Register it in Claude Code

Run this once in your terminal:

```bash
claude mcp add structurizr --transport http http://localhost:3000/mcp
```

Verify it's connected:

```bash
claude mcp list
# structurizr: http://localhost:3000/mcp (HTTP) - ✓ Connected
```

> The MCP tools will appear in Claude Code with a UUID prefix (e.g. `mcp__8dae29da-...`). Use `ToolSearch` in Claude Code to discover and load them dynamically.

### What each flag enables

| Flag | Tools unlocked |
|---|---|
| `-dsl` | validate, parse, inspect |
| `-plantuml` | export-plantuml, export-c4plantuml |
| `-mermaid` | export-mermaid |

---

## Notes

- Docker image `structurizr/structurizr` replaces the deprecated `structurizr/lite` (archived Feb 2026)
- The `local` command is free — no license required
- Edit `workspace.dsl` and refresh the browser; no restart needed
