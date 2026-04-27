[< Back to Guides](README.md)

# OpenSpec — Structured Development Workflow

OpenSpec is the artifact-driven workflow system that keeps agents on track. Instead of giving an agent a vague prompt, you give it a structured pipeline: proposal → design → specs → tasks → implementation.

## Why OpenSpec

Without structure, agents drift. They skip requirements, make inconsistent decisions, and produce code that doesn't match the spec. OpenSpec solves this by breaking work into tracked artifacts with dependencies.

## The Workflow

```
/opsx:explore  →  /opsx:new  →  /opsx:apply  →  /opsx:verify  →  /opsx:archive
```

| Step | Command | What it does |
|------|---------|--------------|
| **Explore** | `/opsx:explore` | Think through the problem before committing — research, read code, surface options. No artifacts created. |
| **New** | `/opsx:new <name>` | Create a change with artifact scaffolding |
| **Fast-Forward** | `/opsx:ff <name>` | Create all artifacts in one go (proposal + design + specs + tasks) |
| **Continue** | `/opsx:continue` | Resume work on the next artifact in sequence |
| **Apply** | `/opsx:apply` | Implement tasks from the change |
| **Verify** | `/opsx:verify` | Check implementation matches specs |
| **Archive** | `/opsx:archive` | Finalize and sync specs |
| **Bulk archive** | `/opsx:bulk-archive` | Archive multiple completed changes at once |
| **Sync** | `/opsx:sync` | Sync delta specs to main without archiving |
| **Onboard** | `/opsx:onboard` | First-time walkthrough of the workflow |

## Artifacts

Each change produces these artifacts in sequence:

| Artifact | Purpose | Contains |
|----------|---------|----------|
| `proposal.md` | Why this change? | Problem, capabilities, impact |
| `specs/*/spec.md` | What should it do? | Requirements with WHEN/THEN scenarios |
| `design.md` | How to build it? | Technical decisions, trade-offs |
| `tasks.md` | What to implement? | Checkboxed task list linked to requirements |

## Quick Example

```bash
# Fast-forward: create all artifacts at once
/opsx:ff add-user-auth

# Implement the tasks
/opsx:apply

# Verify implementation matches specs
/opsx:verify

# Archive when done
/opsx:archive
```

## How Orchestration Uses OpenSpec

During autonomous orchestration, each dispatched agent uses OpenSpec internally:

1. The orchestrator decomposes the spec into changes
2. Each change gets a proposal with scope boundaries
3. The Ralph Loop agent creates remaining artifacts and implements tasks
4. The verify gate checks spec coverage before merge

This is why orchestrated code tends to be well-structured — the agents follow a consistent development methodology.

## OpenSpec CLI

```bash
openspec list                    # show active changes
openspec status --change <name>  # show artifact progress
openspec new change <name>       # create a new change
```

![OpenSpec list](../images/auto/cli/openspec-list.png)

## Spec Preview

Use `openspec status` to see a visual preview of a change's artifact progress:

![Spec preview](../images/auto/cli/spec-preview.png)

## Bulk Operations

When you have completed multiple changes, archive them in batch:

```
/opsx:bulk-archive
```

This archives all changes whose tasks are 100% complete and whose specs have been synced.

To sync spec changes to main without archiving (useful for mid-flight updates):

```
/opsx:sync
```

## Spec-Doc Cross-References

Each documentation page references the openspec specs it covers via HTML comments:

```html
<!-- specs: verify-gate, gate-profiles, orchestration-engine -->
```

When a spec changes, `grep -r "specs:.*verify-gate" docs/` finds all docs that need updating.

## Design Integration

The current design path is **v0.app exports**: `set-design-import` clones a v0 repo, generates `docs/design-manifest.yaml` with shell components, routes, and component bindings, and the dispatcher writes a per-change `openspec/changes/<name>/design.md` slice that the agent reads as `## Design Source` in its `input.md`.

1. **Import** — `set-design-import --git <v0-repo-url> --ref main --scaffold .` pulls the export and generates the manifest.
2. **Hygiene** (optional) — `set-design-hygiene` scans the export for 9 antipatterns (mock arrays, hardcoded strings, broken routes, locale-prefix mismatches) before adoption.
3. **Decompose** — the planner attaches `design_components` and `design_routes` to each change based on entity-reference markers (`@component:NAME`, `@route:/PATH`) in spec files.
4. **Dispatch** — the agent's `input.md` gets a `## Design Source` section pointing to the slice.
5. **Verify** — the `design-fidelity-gate` runs JSX structural parity at merge time. Token mismatches are warnings; component-structure divergence blocks merge with a diff.

Legacy Figma `.make` flow is removed in `v0-only-design-pipeline`. If a project still uses Figma via MCP, the bridge rule treats `design-snapshot.md` as the fallback source — but new projects should use v0.

---

*Next: [Orchestration](orchestration.md) | [Worktrees](worktrees.md) | [Quick Start](quick-start.md)*

<!-- specs: openspec-cli, spec-management, spec-coverage-report, task-traceability, design-pipeline -->
