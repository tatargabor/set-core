[< Back to INDEX](../INDEX.md)

# Architecture

Technical architecture of set-core: layers, module system, profile chain, and state machine.

## System Overview

set-core has four layers: **shell scripts** (`bin/set-*`) for worktree lifecycle, an **orchestration engine** (`set-orchestrate`) for autonomous multi-change execution, a **web dashboard** for monitoring, and an **MCP server** connecting Claude Code agents to the system. Everything is file-based -- no daemon, no database.

```
+-----------------------------------------------------------+
|                   Web Dashboard (port 7400)                |
|  Next.js . real-time status . orchestration control       |
+-----------------------------------------------------------+
|   CLI Tools (bash)         |   MCP Server (python)        |
|   set-new/work/list/merge  |   list_worktrees             |
|   set-loop (Ralph)         |   get_ralph_status            |
|   set-control-sync         |   get_team_status             |
+----------------------------+------------------------------+
|  Orchestration Engine (set-orchestrate)                    |
|  spec -> plan -> dispatch -> monitor -> merge              |
|  parallel worktrees + integration gates + merge queue      |
+-----------------------------------------------------------+
|  Git worktrees + file-based state (JSON)                  |
|  set-control branch for cross-machine team sync           |
+-----------------------------------------------------------+
```

## Three-Layer Module Model

### Layer 1: Core (`lib/set_orch/`)

Abstract orchestration engine. Never contains project-specific logic.

- `profile_types.py` -- `ProjectType` ABC + dataclasses (`VerificationRule`, `OrchestrationDirective`)
- `profile_loader.py` -- `NullProfile`, `CoreProfile` (universal rules), profile resolution chain
- `engine.py` -- orchestration state machine, dispatcher, monitor
- `merger.py` -- merge queue, integration gate execution
- `verifier.py` -- programmatic gate enforcement (lint, e2e, spec-verify)

**Profile resolution order:** entry_points -> direct import -> built-in `modules/` -> NullProfile

### Layer 2: Built-in Modules (`modules/`)

Project-type plugins that ship with set-core. Each is a standalone pip-installable package.

| Module | Class | Inherits | Purpose |
|--------|-------|----------|---------|
| `modules/web/` | `WebProjectType` | `CoreProfile` | Next.js, Playwright, Prisma detection |
| `modules/example/` | `DungeonProjectType` | `CoreProfile` | Reference implementation |

### Layer 3: External Plugins (separate repos)

Private or community plugins registered via `entry_points` in their own `pyproject.toml`. Entry points take priority over built-in modules.

```toml
# External plugin pyproject.toml
[project.entry-points."set_core.project_types"]
fintech = "set_project_fintech:FintechProjectType"
```

## Profile Chain

Profiles provide project-aware behavior through a well-defined interface:

```
NullProfile (no-op fallback)
  +-- CoreProfile (universal rules: file-size, no-secrets, todo-tracking)
        +-- WebProjectType (web: IDOR checks, auth middleware, Playwright)
        +-- DungeonProjectType (example: reference patterns)
        +-- FintechProjectType (external: PCI compliance, IDOR rules)
```

Key methods on the `ProjectType` ABC:

| Method | Purpose |
|--------|---------|
| `detect_test_command()` | Find the project's test runner |
| `detect_e2e_command()` | Find E2E test command |
| `get_forbidden_patterns()` | Patterns that fail the lint gate |
| `get_verification_rules()` | Rules enforced during verify |
| `get_orchestration_directives()` | Directives injected into orchestration config |
| `post_merge_install()` | Commands to run after merge (e.g., `pnpm install`) |

## Orchestration State Machine

Each change progresses through a state machine:

```
planned -> dispatched -> running -> done -> merged
                  \               /        |
                   failed    merge-blocked  archived
                      |
                   (retry or abandon)
```

**States:**

| State | Meaning |
|-------|---------|
| `planned` | In the plan, not yet dispatched |
| `dispatched` | Worktree created, agent starting |
| `running` | Agent actively working |
| `done` | Agent finished, awaiting merge |
| `merged` | Successfully merged to main |
| `merge-blocked` | Merge conflict or gate failure |
| `failed` | Agent failed, may retry |
| `archived` | Completed and cleaned up |

## Integration Gates

All merges go through the gate pipeline -- never `git merge` manually:

```
done -> dep-install -> build -> test -> e2e -> code-review -> merge
```

Each gate is profile-driven: the active `ProjectType` determines what commands run. If a gate fails, the change moves to `merge-blocked` and the agent can fix and retry.

### E2E gate self-heal marker

When the web e2e gate detects a `MODULE_NOT_FOUND` crash for a package declared in `package.json` (e.g. the agent added a dep to `package.json` but forgot `pnpm install`), the gate runs install and reruns Playwright once in-gate. Successful self-heal prepends `[self-heal: installed <pkg>]` to `GateResult.output` -- forensics (`set-run-logs`) and the web dashboard use this marker to distinguish healed runs from natural passes. Self-heal does NOT consume a `verify_retry_count` slot, and runs at most once per gate invocation. Implementation: `modules/web/set_project_web/gates.py`. Spec: `e2e-dep-drift-guard`.

## Technologies

| Component | Technology | Why |
|-----------|------------|-----|
| CLI tools | Bash | Zero dependencies, fast |
| Orchestration | Python + Claude LLM | Spec decomposition, parallel dispatch |
| Web dashboard | Next.js + React | Real-time monitoring UI |
| MCP server | Python (FastMCP) | Exposes data to Claude Code |
| State | JSON files + git | No database needed |
| Team sync | Git branch (`set-control`) | No server -- push/pull via git |
| Encryption | NaCl Box (libsodium) | E2E encrypted team chat |
| Memory | RocksDB (via shodh-memory) | Per-project semantic search |

## Nested Agent Collaboration

set-core orchestrates across worktrees while Claude Code Agent Teams work within a single worktree:

```
set-core (outer loop -- git-level isolation)
  +-- Worktree A (branch: add-auth)
  |     +-- Agent Teams: lead + implement + test + docs
  +-- Worktree B (branch: fix-api)
  |     +-- Agent Teams: lead + fix + test
  +-- Cross-machine sync via set-control git branch
```

- **Agent Teams** = parallelism within a worktree
- **set-core** = parallelism across worktrees
- **Together** = nested parallelism with full git isolation

## Key Directories

| Path | Contents |
|------|----------|
| `lib/set_orch/` | Core engine (Layer 1) |
| `modules/web/` | Web project type plugin (Layer 2) |
| `modules/example/` | Reference plugin |
| `bin/` | CLI tools |
| `.claude/rules/` | Rules for set-core development |
| `.claude/skills/` | Slash command implementations |
| `templates/core/rules/` | Core rules deployed to consumer projects |
| `openspec/` | Specs and changes |
| `mcp-server/` | MCP server (FastMCP) |
| `web/` | Web dashboard (Next.js) |

---

<!-- Spec cross-references:
  - openspec/specs/orchestration-engine.md (state machine, dispatcher, merger)
  - openspec/specs/profile-system.md (3-layer model, profile chain)
  - openspec/specs/worktree-management.md (git worktree lifecycle)
  - openspec/specs/team-sync.md (set-control branch, cross-machine)
-->

*See also: [CLI Reference](cli.md) · [Configuration](configuration.md) · [Plugins](plugins.md)*

<!-- specs: modular-source-structure, profile-loader, execution-model -->
