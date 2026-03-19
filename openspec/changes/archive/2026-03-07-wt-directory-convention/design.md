## Context

set-core consumer projects currently store wt-related files in scattered locations:
- `.claude/orchestration.yaml` — hidden directory, mixed with Claude-specific config
- `project-knowledge.yaml` — project root, no namespace
- `docs/orchestration-runs/*.md` — mixed with general docs
- No defined location for: requirements, knowledge patterns, lessons learned

The OpenSpec project solved this same problem with a dedicated `openspec/` directory. We follow the same pattern.

## Goals / Non-Goals

**Goals:**
- Standardized `wt/` directory in consumer projects for all set-core artifacts
- `set-project init` scaffolds the structure automatically
- Backward-compatible: existing file locations work as fallback
- Planner, dispatcher, verifier find files in new locations
- Simple migration path for existing projects

**Non-Goals:**
- Plugin system implementation (future change, wt-web/wt-spec-capture)
- Requirement registry logic/workflow (this change defines the directory and format only)
- Changing the OpenSpec directory structure
- Auto-migration without user consent
- MCP server tools for querying `wt/requirements/` or `wt/knowledge/` (future change — agents access these via file reads for now)

## Decisions

### Decision 1: Directory Layout

```
wt/
  ├── orchestration/
  │   ├── config.yaml          ← orchestration directives (was .claude/orchestration.yaml)
  │   ├── runs/                ← run logs (was docs/orchestration-runs/)
  │   └── plans/               ← saved plan JSONs (new — plan history)
  │
  ├── knowledge/
  │   ├── project-knowledge.yaml  ← feature registry, cross-cutting files (was ./project-knowledge.yaml)
  │   ├── patterns/            ← project-specific code patterns (new)
  │   └── lessons/             ← extracted learnings from runs (new)
  │
  ├── requirements/
  │   └── *.yaml               ← business requirement files (new)
  │
  ├── plugins/
  │   └── <plugin-name>/       ← plugin-specific workspace (new)
  │       └── ...              ← plugin defines its own structure
  │
  └── .work/                   ← gitignored temp workspace (new)
      └── ...                  ← scratch files, caches, intermediate state
```

**Why this layout:**
- `orchestration/` groups all sentinel/orchestrator artifacts — config, history, plans
- `knowledge/` groups what agents need to know about the project
- `requirements/` is the business layer — input for spec generation
- `plugins/` gives each plugin its own workspace for data, state, and artifacts
- Flat top-level mirrors `openspec/` simplicity (4 subdirs, not deeply nested)

**Alternative considered:** Putting requirements inside `openspec/`. Rejected because requirements are a business input layer that exists before and after OpenSpec changes — they're not artifacts of the change workflow.

### Decision 2: Lookup Chain (Backward Compatibility)

All set-core components use a fallback chain when looking for files:

```
1. wt/orchestration/config.yaml    → .claude/orchestration.yaml     → defaults
2. wt/knowledge/project-knowledge.yaml → ./project-knowledge.yaml   → skip
3. wt/orchestration/runs/          → docs/orchestration-runs/       → skip
```

Implementation: a single shell function `wt_find_config()` in `lib/orchestration/state.sh`:

```bash
wt_find_config() {
    local name="$1"
    case "$name" in
        orchestration)
            if [[ -f "wt/orchestration/config.yaml" ]]; then
                echo "wt/orchestration/config.yaml"
            elif [[ -f ".claude/orchestration.yaml" ]]; then
                echo ".claude/orchestration.yaml"
            fi
            ;;
        project-knowledge)
            if [[ -f "wt/knowledge/project-knowledge.yaml" ]]; then
                echo "wt/knowledge/project-knowledge.yaml"
            elif [[ -f "project-knowledge.yaml" ]]; then
                echo "project-knowledge.yaml"
            fi
            ;;
    esac
}
```

**Why not symlinks:** Symlinks cause issues with git (tracked vs untracked), and the fallback chain is explicit and debuggable.

### Decision 3: Scaffolding in set-project init

`set-project init` gains a new step after deployment:

1. Create `wt/` directory structure (mkdir -p for each subdir)
2. Detect existing files in legacy locations
3. If found, print migration suggestion (don't auto-move):
   ```
   Found legacy files:
     .claude/orchestration.yaml → wt/orchestration/config.yaml
     project-knowledge.yaml → wt/knowledge/project-knowledge.yaml

   Run 'set-project migrate' to move them.
   ```
4. A separate `set-project migrate` command handles the actual move + git mv

**Why separate migrate command:** `set-project init` is already used for re-deployment (re-running updates). Adding auto-migration would be risky for existing workflows. Explicit migration is safer.

### Decision 4: Requirements File Format

```yaml
# wt/requirements/REQ-001-user-auth.yaml
id: REQ-001
title: User Authentication
status: planned          # captured | planned | in_progress | implemented | deferred
priority: must           # must | should | could
source: manual           # manual | wt-spec-capture | stakeholder
description: |
  Users need to authenticate with email and password.
  Social login (Google, GitHub) is a should-have.

acceptance_criteria:
  - User can register with email + password
  - User can log in and receive a session
  - User can reset password via email

links:
  changes: [user-auth, password-reset]    # OpenSpec change names
  specs: [user-auth]                       # OpenSpec spec names
  features: [auth]                         # project-knowledge feature names

created: 2026-03-07
updated: 2026-03-07
```

**Why YAML:** Consistent with orchestration.yaml and project-knowledge.yaml. Machine-parseable, human-readable.

**Why not markdown:** Requirements need structured fields (status, priority, links) that are awkward in markdown frontmatter and easy in YAML.

**Why file-per-requirement:** Easy to git-track individual requirement lifecycle. No merge conflicts when multiple requirements change. Simple globbing for status queries.

### Decision 5: Run Logs Location

Run logs move from `docs/orchestration-runs/` to `wt/orchestration/runs/`. Format stays the same (markdown).

Saved plan JSONs go to `wt/orchestration/plans/` with naming: `plan-v{N}-{date}.json`. This preserves plan history that currently gets overwritten by `orchestration-plan.json`.

### Decision 6: Plugin Workspace Directory

Each set-core plugin (e.g., wt-web, wt-spec-capture) gets its own workspace under `wt/plugins/<plugin-name>/`. The plugin defines its own internal structure.

```
wt/plugins/
  ├── wt-spec-capture/       ← chrome extension workspace
  │   ├── captures/          ← scraped site data, annotated DOM snapshots
  │   ├── drafts/            ← generated spec drafts before export to requirements/
  │   └── config.yaml        ← plugin-specific settings
  │
  └── wt-web/                ← web knowledge plugin workspace
      ├── framework.yaml     ← detected framework config
      └── analysis/          ← project analysis results
```

**Why under `wt/plugins/`:**
- Plugins are part of the wt ecosystem, so they live under `wt/`
- Each plugin gets a namespace to avoid collisions between plugins
- The plugin controls its own internal structure — set-core only creates the parent directory
- `set-project add-plugin <name>` would create `wt/plugins/<name>/` and run plugin-specific init

**Convention:** Plugin workspace is for plugin-generated data and state. Plugin *rules* and *skills* go into `.claude/` via the normal deployment mechanism.

### Decision 7: Gitignored Work Directory

`wt/.work/` is a gitignored scratch space for temporary files that shouldn't be version-controlled:
- Intermediate build/analysis results
- Plugin caches (e.g., spec-capture DOM snapshots before review)
- Orchestrator working files (plan drafts, spec summaries in progress)
- Agent scratch space during execution

**Why `.work/` (dot prefix):** Signals "not user-facing content" — same convention as `.git/`, `.claude/`. Sorted before regular directories.

**Why not system `/tmp/`:** Project-scoped temp files are easier to find, survive reboots, and can be cleaned with `rm -rf wt/.work/*`.

Scaffolding adds `wt/.work/` to `.gitignore` automatically.

### Decision 8: Memory Integration with wt/

The memory system (shodh-memory via set-memory) currently lives entirely outside the project tree (`~/.set-core/memory/<project>/`). This change connects it to `wt/` in three ways:

**A. Memory Seed File — `wt/knowledge/memory-seed.yaml` (versioned)**

Project-essential memories that every developer/agent should start with. Committed to git, imported on `set-project init` or `set-memory seed`.

```yaml
# wt/knowledge/memory-seed.yaml
version: 1
seeds:
  - type: Context
    content: "This project uses Laravel 11 with Inertia.js and Vue 3"
    tags: "framework,stack"
  - type: Decision
    content: "All API endpoints use Form Requests for validation"
    tags: "api,validation,convention"
  - type: Learning
    content: "Sidebar component must be updated when adding new pages"
    tags: "cross-cutting,sidebar"
```

**Why seed files:**
- New team member clones repo → `set-project init` → memory has project fundamentals
- Fresh memory store (after cleanup/reset) → re-seed without losing project knowledge
- Versioned → team reviews what's considered "essential project knowledge"
- Small — 10-30 seeds, not a full memory dump

**Import behavior:**
- `set-project init` checks if seeds exist and memory is empty → auto-import
- `set-memory seed` command for explicit re-import (skips duplicates via content hash)
- Seeds tagged `source:seed` for traceability

**B. Memory Sync Working Directory — `wt/.work/memory/` (gitignored)**

The `set-memory sync push/pull` currently uses temp dirs. Move working files to `wt/.work/memory/`:
- `wt/.work/memory/export.json` — last export before push
- `wt/.work/memory/import-staging/` — pulled data before import
- `wt/.work/memory/.sync-state` — sync state tracking (was in memory store dir)

**Why:** Project-scoped, visible, debuggable. Doesn't clutter `/tmp/`.

**C. Knowledge → Memory Bridge (future consideration)**

The `wt/knowledge/lessons/` files (versioned markdown) and the memory store (runtime RocksDB) serve complementary purposes:

```
wt/knowledge/lessons/       ← curated, versioned, team-shared
        ↕ (manual)
~/.set-core/memory/         ← runtime, per-machine, auto-accumulated
```

For now: no auto-sync between them. Lessons are manually written/curated. Memory is auto-accumulated. A future `set-memory export-lessons` could extract high-value memories into `wt/knowledge/lessons/`.

## Risks / Trade-offs

- **[Risk] Existing scripts hardcode paths** → Mitigation: fallback chain ensures old paths still work. Deprecation warnings guide migration.
- **[Risk] `wt/` conflicts with project's own directory** → Mitigation: unlikely name collision. If happens, could make configurable (but YAGNI for now).
- **[Risk] Requirements format might evolve** → Mitigation: version field in format. Start simple, extend later.
- **[Trade-off] Two valid locations for config during migration** → Acceptable: fallback chain is deterministic (wt/ wins). Migration is one-time.

## Resolved Questions

- **Plan archiving:** Auto-save on every plan generation (task 5.1). Plans are small JSON files, no cleanup needed.
- **Lessons population:** Manually curated for now. A future `set-memory export-lessons` could auto-extract, but premature to build before the directory convention is established.
