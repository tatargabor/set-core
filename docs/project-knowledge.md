# Project Knowledge System

`project-knowledge.yaml` provides project-specific context to the orchestrator for smarter planning, dispatch, and verification.

## Scaffolding

```bash
cd /path/to/your-project
wt-project init-knowledge
```

This scans the project for common cross-cutting patterns (i18n files, sidebar/navigation components, route definitions, database schemas) and generates a draft `project-knowledge.yaml` at the repo root.

Review and edit the generated file — the auto-scan finds common patterns but your project may have additional cross-cutting files.

## Schema Reference

```yaml
version: 1

cross_cutting_files:
  - path: src/i18n/en.json
    description: English translations — every user-facing feature adds keys
  - path: src/components/Sidebar.tsx
    description: Navigation sidebar — most features add entries here

features:
  dashboard:
    touches:
      - src/pages/Dashboard.tsx
      - src/components/dashboard/
    description: Main dashboard page with widgets
    reference_impl: false

verification_rules:
  - name: i18n-completeness
    trigger: "src/i18n/*.json"
    check: "all language files have same keys"
    severity: error
  - name: sidebar-order
    trigger: "src/components/Sidebar.tsx"
    check: "sidebar items are in alphabetical order"
    severity: warning
```

### `cross_cutting_files`

Files that multiple features touch. Used by:

- **Planner** (`check_scope_overlap`) — detects when parallel changes would modify the same cross-cutting file, injecting merge hazard warnings into the planning prompt
- **Planner** (`cmd_plan`) — includes cross-cutting file context in the decompose prompt so the LLM can plan accordingly

Each entry has:
- `path` — relative path from repo root (exact file or directory)
- `description` — why this file is cross-cutting

### `features`

Maps logical features to their file scopes. Used by:

- **Dispatcher** (`dispatch_change`) — injects `touches` file content into the change proposal for targeted context
- **Dispatcher** — when `reference_impl: true`, includes the feature path as a reference implementation

Each feature has:
- `touches` — list of file paths/directories this feature owns
- `description` — what the feature does
- `reference_impl` — (optional, default false) if true, the feature's files serve as a reference for similar implementations

### `verification_rules`

Automated checks triggered by file path patterns in `git diff`. Evaluated after tests pass, before merge. Used by:

- **Verifier** (`evaluate_verification_rules`) — matches trigger globs against modified files, then checks the described condition

Each rule has:
- `name` — identifier for the rule
- `trigger` — glob pattern matching modified files (e.g., `src/i18n/*.json`)
- `check` — human-readable description of what to verify (evaluated by the LLM reviewer)
- `severity` — `error` (blocks merge) or `warning` (logged, non-blocking)

## Graceful Degradation

All features no-op when `project-knowledge.yaml` is absent:
- Planner skips cross-cutting hazard analysis
- Dispatcher skips targeted context injection
- Verifier skips verification rules

No configuration is required to run orchestration without project knowledge.

## Cross-Cutting Checklist

Running `init-knowledge` also deploys `.claude/rules/cross-cutting-checklist.md` — a rule template that reminds agents to check cross-cutting files when their changes touch matching paths. The checklist uses path-scoped frontmatter to activate only for relevant file patterns.
