[< Back to README](../README.md)

# Developer Memory

Per-project cognitive memory for AI agents. Agents save decisions, learnings, and context as they work — future agents in different sessions recall relevant past experience before starting. Built on [shodh-memory](https://github.com/varun29ankuS/shodh-memory), integrated across CLI, GUI, and OpenSpec workflows.

> **Status:** Experimental. Requires `pip install 'shodh-memory>=0.1.75,!=0.1.80'`. Gracefully degrades if not installed — all commands silently no-op.

---

## Brownfield Project? Seed Memory from Existing Docs

If you're joining a project that already has OpenSpec artifacts (proposals, designs, specs) but empty memory, use the **[Memory Seeding Guide](memory-seeding-guide.md)** to bootstrap project memory from existing documentation. An AI agent reads each artifact, extracts decisions, learnings, and context, and saves them via `set-memory`. One-time process — takes a few minutes and gives future agents immediate access to past project knowledge.

---

## Quick Start

```bash
# 1. Check if memory is available
set-memory health

# 2. Save something
echo "PySide6 QTimer must only be called from the main thread" \
  | set-memory remember --type Learning --tags pyside6,threading

# 3. Search for it later
set-memory recall "QTimer threading"
```

That's it. The memory is stored per-project (worktrees of the same repo share memory) and persists across sessions.

---

## How set-memory Differs from Claude Code Memory

Claude Code has its own [built-in memory system](https://docs.anthropic.com/en/docs/claude-code/memory): `CLAUDE.md` files for team-shared instructions and auto memory (`~/.claude/projects/<project>/memory/MEMORY.md`) for Claude's own notes. set-memory is **complementary, not a replacement** — they serve different roles.

**CLAUDE.md / auto memory = instructions.** Always loaded at session start, deterministic, tells agents how to behave. "Use pytest", "2-space indent", "run tests with PYTHONPATH=."

**set-memory = experience.** Searched on demand when relevant, semantic, tells agents what happened before. "RocksDB crashes with concurrent access — use file locking", "We chose SSE over WebSocket because Cloudflare Workers don't support persistent connections."

| Aspect | Claude Code Memory | set-memory |
|---|---|---|
| **Storage** | Markdown files | RocksDB + vector embeddings |
| **Recall** | Loaded at startup (200-line cap on auto memory) | Semantic search on demand (scales to 1000s) |
| **Structure** | Freeform text | Typed (Decision / Learning / Context) + tags |
| **Worktrees** | Separate memory per worktree | Shared across worktrees of the same repo |
| **Team sharing** | CLAUDE.md in git (manual) | `set-memory sync push/pull` |
| **Lifecycle** | Edit files manually | audit, dedup, forget, export/import |
| **Workflow hooks** | None (always loaded) | OpenSpec hooks at every phase (recall + save) |

The worktree difference is significant: Claude's auto memory gives each worktree its own isolated memory directory. An agent on `feature-a` doesn't see what an agent on `feature-b` learned. set-memory shares across all worktrees of the same repo by design — knowledge from any branch is available everywhere (with branch-boost for relevance).

> **When to use which:** Put stable rules and conventions in CLAUDE.md. Let set-memory capture the messy, evolving knowledge — past failures, decisions with rationale, non-obvious gotchas — that accumulates as agents work on the project over time.

---

## When Is It Useful?

### 1. Avoiding repeated mistakes

You spent an afternoon debugging why RocksDB corrupts data when two agents write simultaneously. You fixed it with file locking. A month later, a different agent starts a related change.

```bash
# You (or the agent) saves the hard-won knowledge:
echo "RocksDB crashes with concurrent access from multiple processes. \
Must use /tmp/set-memory-<project>.lock for file locking." \
  | set-memory remember --type Learning --tags rocksdb,concurrency

# A month later, new session, new agent starts a change:
#   /opsx:new "optimize memory storage"
#
# The OpenSpec hook runs automatically:
#   set-memory recall "optimize memory storage" --limit 3
#
# Agent sees:
#   Learning: RocksDB crashes with concurrent access from multiple
#   processes. Must use /tmp/set-memory-<project>.lock for file locking.
#
# → Agent uses file locking from the start. No wasted afternoon.
```

**Best for:** Preventing the same failure from happening twice. Especially valuable when multiple people or agents work on the same project over time.

### 2. Project decisions

Your team decided to use SSE instead of WebSockets for the notification system because the infrastructure doesn't support persistent connections. Three months later, someone starts a "real-time updates" feature.

```bash
# Decision saved during the original discussion:
echo "Chose SSE over WebSocket for notifications. \
Our infra (Cloudflare Workers) doesn't support persistent connections." \
  | set-memory remember --type Decision --tags architecture,notifications,sse

# Three months later:
#   /opsx:new "add real-time updates"
#
# Automatic recall finds:
#   Decision: Chose SSE over WebSocket for notifications.
#   Our infra doesn't support persistent connections.
#
# → Agent designs the feature using SSE, not WebSocket.
```

**Best for:** Architectural decisions, technology choices, "why did we do it this way" context that's easy to forget.

### 3. Technical gotchas

Mid-implementation, you tell the agent something non-obvious about the codebase. The agent recognizes it as valuable and saves it automatically.

```
You: "By the way, the FeatureWorker polls every 15 seconds, so don't
     expect instant updates in the GUI after a status change."

Agent recognizes this as a technical learning and saves it:
  [Memory saved: Learning — FeatureWorker polls every 15s, GUI updates not instant]

# Next time any agent works on GUI responsiveness:
#   set-memory recall "GUI update delay"
#   → Learning: FeatureWorker polls every 15 seconds...
```

**Best for:** Non-obvious behaviors, API quirks, timing dependencies, "things you'd tell a new team member."

### 4. Background context for future agents

You're setting up a new project with unusual constraints. Save the context so future agents don't start from zero.

```bash
echo "This project uses a monorepo with pnpm workspaces. \
The API is in packages/api/, the frontend in packages/web/. \
Tests must run from the root with 'pnpm test --filter=<package>'." \
  | set-memory remember --type Context --tags setup,monorepo,pnpm

# Every future agent session can recall this:
set-memory recall "project structure"
# → Context: This project uses a monorepo with pnpm workspaces...
```

**Best for:** Project setup notes, deployment procedures, environment-specific constraints, onboarding context.

---

## Memory Types

| Type | When to use | Example |
|------|-------------|---------|
| **Decision** | A choice was made between alternatives | "Chose SQLite over PostgreSQL for local storage because no server dependency" |
| **Learning** | A pattern, gotcha, or lesson was discovered | "pytest fixtures with module scope don't reset between test files" |
| **Context** | Background info that provides orientation | "This repo deploys to AWS Lambda via CDK, pipeline in infra/ directory" |

**Legacy aliases:** `Observation` maps to `Learning`, `Event` maps to `Context`. These still work but print a deprecation warning.

### Phase Tags (Orchestration)

When memories are created during orchestration, they are tagged with a phase to enable filtered recall:

| Tag | Source | Recalled during |
|-----|--------|-----------------|
| `phase:planning` | Decomposition learnings | Planning/decomposition |
| `phase:execution` | Worker agent learnings | Change dispatch |
| `phase:verification` | Test/review/smoke results | Verification retries |
| `phase:orchestration` | Operational decisions (replan, merge) | Iteration replans |
| `phase:merge` | Merge outcomes | Merge conflict resolution |
| `phase:test` | Test pass/fail results | Test retries |
| `phase:review` | Code review results | Review retries |
| `phase:post-merge` | Post-merge pipeline results | Post-merge fixes |

The `orch_recall` function filters by phase tag, so planning memories don't leak into execution and vice versa.

Memories tagged `stale:true` are excluded from all orchestrator recall.

---

## Branch Awareness

Every memory is automatically tagged with the git branch it was created on. This provides branch context without isolating knowledge.

### How it works

- `set-memory remember` auto-appends `branch:<current-branch>` tag (e.g., `branch:master`, `branch:change/add-auth`)
- `set-memory recall` boosts results from the current branch (they appear first), but still returns cross-branch results
- If not in a git repo or on a detached HEAD, the branch tag is silently skipped

### Scenarios

| Scenario | Remember | Recall |
|---|---|---|
| Working on `master` | Tagged `branch:master` | Boost master memories |
| Feature branch `change/xyz` | Tagged `branch:change/xyz` | Boost change/xyz, master results also returned |
| Parallel worktrees | Each tags with its own branch | Cross-branch memories visible (lower priority) |
| After branch merge | Memories keep original branch tag | Findable from any branch |
| Branch dropped | Memories persist with branch tag | Learnings not lost |
| Detached HEAD | No branch tag | No boost (flat recall) |
| Explicit `--tags` on recall | n/a | Branch boost skipped (user filter takes priority) |

### Override

If you pass `--tags branch:custom` explicitly to `remember`, the auto-tag is skipped (no duplicate).

---

## Memory Migrations

When the memory storage format evolves (e.g., adding branch tags to existing memories), migrations transform the data automatically.

### Auto-migration

On the first `set-memory` command after an upgrade, pending migrations run automatically:

```
$ set-memory list
Migrating memory storage... done (1 migration(s) applied)
[...]
```

Use `--no-migrate` to skip: `set-memory --no-migrate list`

### Manual control

```bash
# Run pending migrations
set-memory migrate

# Check migration status
set-memory migrate --status
```

### Migration 001: Branch tags

The first migration adds `branch:unknown` to all pre-existing memories that don't have a `branch:*` tag. This is non-destructive — no data is lost, only a tag is added.

---

## Hook-Driven Memory (5 Layers)

Memory is fully automated via Claude Code hooks — no agent discipline required, no inline skill instructions needed. Five layers cover the complete agent lifecycle:

```
  ┌─────────────────────────────────────────────────────────────┐
  │                    SESSION TIMELINE                          │
  │                                                              │
  │  Session Start                                               │
  │  ┌────────────────────────────────────────────┐              │
  │  │ L1: set-hook-memory-warmstart               │              │
  │  │  • Load cheat-sheet memories               │              │
  │  │  • Discover project hot topics             │              │
  │  │  • Inject proactive project context        │              │
  │  └────────────────────────────────────────────┘              │
  │       ↓                                                      │
  │  Every User Prompt                                           │
  │  ┌────────────────────────────────────────────┐              │
  │  │ L2: set-hook-memory-recall                  │              │
  │  │  • Extract topic from prompt text          │              │
  │  │  • Recall relevant memories                │              │
  │  │  • Inject as additionalContext             │              │
  │  └────────────────────────────────────────────┘              │
  │       ↓                                                      │
  │  Before Hot-Topic Bash Commands                              │
  │  ┌────────────────────────────────────────────┐              │
  │  │ L3: set-hook-memory-pretool                 │              │
  │  │  • Pattern-match against discovered topics │              │
  │  │  • Recall command-specific memories        │              │
  │  │  • Skip non-matching (< 5ms overhead)      │              │
  │  └────────────────────────────────────────────┘              │
  │       ↓                                                      │
  │  On Bash Errors                                              │
  │  ┌────────────────────────────────────────────┐              │
  │  │ L4: set-hook-memory-posttool                │              │
  │  │  • Parse error text as recall query        │              │
  │  │  • Surface past fixes for this error       │              │
  │  │  • Auto-promote command to hot topics      │              │
  │  └────────────────────────────────────────────┘              │
  │       ↓                                                      │
  │  Session End                                                 │
  │  ┌────────────────────────────────────────────┐              │
  │  │ L5: set-hook-memory-save                    │              │
  │  │  • Haiku extracts session insights         │              │
  │  │  • Promotes conventions to cheat-sheet     │              │
  │  │  • Extracts design choices from commits    │              │
  │  └────────────────────────────────────────────┘              │
  └─────────────────────────────────────────────────────────────┘
```

### Layer detail

| Layer | Hook Event | Script | When | Latency |
|-------|-----------|--------|------|---------|
| L1 | SessionStart | `set-hook-memory-warmstart` | Once at session start | ~500ms |
| L2 | UserPromptSubmit | `set-hook-memory-recall` | Every user prompt | ~200ms |
| L3 | PreToolUse (Bash) | `set-hook-memory-pretool` | Hot-topic Bash match | 2ms (skip) / 150ms (match) |
| L4 | PostToolUseFailure (Bash) | `set-hook-memory-posttool` | Bash errors only | ~200ms |
| L5 | Stop | `set-hook-memory-save` | Every stop (background) | 5-10s (async) |

### Hot-topic discovery

L3 only fires on commands that match hot-topic patterns. Patterns come from two sources:

**At session start (L1 discovers):**
- `bin/*` scripts → command prefixes (e.g., `wt-*`, `openspec`)
- `package.json` / `Makefile` / `pyproject.toml` → project commands
- Memory tags → frequently-discussed topics
- Error memories → commands that failed before

**Mid-session (L4 promotes):**
- When a Bash command fails, L4 extracts its prefix and adds it to the hot-topics cache
- Next time that command runs, L3 will match and inject context

Generic base patterns (always active): `ssh`, `rm -rf`, `sudo`, `docker/kubectl`

Cache file: `.claude/hot-topics.json`

### Cheat sheet

Memories tagged `cheat-sheet` are loaded at every session start by L1 and injected as `=== OPERATIONAL CHEAT SHEET ===` context. This is the **emergent soft conventions** layer — productivity patterns discovered during work, not hard constraints.

**How content gets in:**

| Path | When |
|---|---|
| L5 auto-extraction | Session end — Haiku extracts `Convention` or `CheatSheet` type entries from session transcript |
| Manual emphasis | `echo "..." \| set-memory remember --type Learning --tags cheat-sheet,...` |

**What belongs here:**
- Recurring commands with non-obvious flags: `PYTHONPATH=. pytest tests/gui/`
- Project-specific build/test procedures
- Common error→fix patterns that apply broadly
- Environment setup quirks discovered in the field

**What does NOT belong here** (use `set-memory rules` instead):
- Credentials and login details
- Mandatory pre-checks or deployment gates
- Hard constraints that must always be enforced

**Curation:**

```bash
# See what's in cheat-sheet
set-memory recall "operational" --tags "cheat-sheet" --limit 10

# List all cheat-sheet entries
set-memory list --type Learning | python3 -c "
import json, sys
for m in json.load(sys.stdin):
    if 'cheat-sheet' in m.get('tags',''):
        print(m['id'][:8], m['content'][:80])
"

# Remove a bad entry
set-memory forget <id>

# Add one manually
echo "Run GUI tests with: PYTHONPATH=. python -m pytest tests/gui/ -v --tb=short" \
  | set-memory remember --type Learning --tags cheat-sheet,testing
```

**Capacity:** L1 loads up to 5 cheat-sheet entries per session. L5 extracts at most 2 new entries per session to prevent bloat.

### Skills and CLAUDE.md

Skills (OpenSpec) contain **no inline memory instructions**. The hooks handle everything:
- L2 replaces skill-level "recall past experience" steps
- L5 replaces skill-level "save insights" and "agent self-reflection" steps
- CLAUDE.md's "Persistent Memory" section explains the system; agent uses `set-memory remember` only for emphasis

### L5 detail (Stop hook)

**PATH 1 — Transcript extraction** (via Haiku LLM): Extracts insights from the active Claude session transcript. Uses a staging+debounce pattern to avoid duplicate memories:
1. Writes extracted insights to a staging file (`.set-core/.staged-extract-{transcript-id}`)
2. Each Stop event overwrites the same staging file — only the latest extraction persists
3. Skips Haiku extraction if the staging file was written less than 5 minutes ago (debounce)
4. When a *different* transcript is detected (new session), commits the previous staging file to `set-memory` and starts staging for the new transcript
5. Staged files older than 1 hour are auto-committed (handles "last session in project")

**PATH 2 — Design choice extraction**: Detects new git commits, extracts **Choice** lines from `design.md`, and saves ONE concise Decision memory per change (~300 chars max). Idempotent — won't re-save for the same change.

### Deployment

All 5 hooks are deployed automatically via `set-deploy-hooks`. Use `set-deploy-hooks --no-memory` to skip memory hooks (e.g., for benchmark baselines). All hooks self-degrade gracefully — they exit 0 immediately if `set-memory` is not installed.

---

## GUI

The Control Center GUI provides memory access through the project header's context menu.

![Status badges in the Control Center — M (Memory), O (OpenSpec), R (Ralph)](images/control-center-memory.png)

*The "Extra" column shows per-project status badges: **M** (memory available, blue), **O** (OpenSpec initialized, teal), **R** (Ralph loop running, red).*

### [M] button tooltip

The `[M]` indicator in the project header row shows memory status. Hover to see: memory count, availability, and whether OpenSpec hooks are installed.

### Browse Memories

**Menu → Memory → Browse Memories...**

Opens a dialog with two view modes:

- **Summary mode** (default) — context summary grouped by category (Decisions, Learnings, Context). Shows the top 5 items per category via `set-memory context`. Opens instantly regardless of memory count.
- **List mode** — paginated card list showing all memories, 50 at a time. Click "Load More" to see the next batch. Data is fetched once and cached; subsequent pages render from cache without new subprocess calls.

Toggle between views with the **"Show All"** / **"Summary"** button.

Both views share:
- **Search bar** — semantic search across all memories (uses `set-memory recall`, up to 20 results). Search overrides either view; "Clear" returns to the previous view mode.
- **Export button** — export all project memories to a JSON file. Opens a directory picker; file is auto-named `<project>-memory-<date>.json`.
- **Import button** — import memories from a JSON export file. Opens a file picker (JSON filter); shows imported/skipped counts. Duplicate detection prevents re-importing the same memories.
- **Card display** — each memory shown with type badge (Learning=green, Decision=blue, Context=amber), content preview, tags, and creation date.
- **Status bar** — shows view mode and memory count.

### Remember Note

**Menu → Memory → Remember Note...**

Quick way to save a memory from the GUI:
- Select type (Learning / Decision / Context)
- Enter content (multi-line)
- Add tags (optional, comma-separated)

---

## Rules — Deterministic Operational Constraints

Semantic memory is probabilistic. For high-stakes constraints that **must** be surfaced every time — credentials, mandatory pre-checks, hard deployment gates — use the Rules system instead.

Rules are stored in `.claude/rules.yaml` at the project root, matched by keyword against the user prompt, and injected as a `MANDATORY RULES` section **before** project memory on every matching prompt. No shodh-memory dependency — works even without it installed.

```bash
# Add a rule
set-memory rules add --topics "customer,sql" \
  "Use login customer_ro / password XYZ123 for customer table queries"

# List rules
set-memory rules list

# Remove a rule
set-memory rules remove <id>
```

The `.claude/rules.yaml` format:

```yaml
rules:
  - id: sql-customer-login
    topics: [customer, sql]
    content: |
      Use customer_ro / XYZ123 for customer table queries.
      Never use other credentials.
```

**Rules vs cheat-sheet:** Rules are explicit, deterministic, committed to git. Use them for mandatory constraints. Cheat-sheet is emergent, probabilistic, for soft conventions. Don't put credentials or hard constraints in cheat-sheet — they may not appear when needed.

| | Rules | Cheat-sheet |
|---|---|---|
| **Trigger** | Topic keyword match | Session start (L1) |
| **Guarantees** | Always injected when topic matches | Loaded at session start only |
| **Use for** | Credentials, mandatory gates, hard constraints | Soft conventions, command patterns |
| **Storage** | `.claude/rules.yaml` (git) | shodh-memory (DB) |
| **How added** | `set-memory rules add` (explicit) | L5 haiku extraction (automatic) |

---

## Emphasis Memory

The hooks handle automatic recall and save. Agents can additionally use explicit `set-memory remember` for high-importance items — things the automatic extraction might miss or that need immediate emphasis:

- Critical user decisions or preferences
- Non-obvious gotchas discovered during investigation
- Project constraints that affect future work

```
echo "PySide6 QTimer must only be called from the main thread" \
  | set-memory remember --type Learning --tags pyside6,threading
```

Use `set-memory forget <id>` to suppress or correct wrong memories.

---

## CLI Reference

### set-memory

**Core Commands:**

| Command | Description |
|---------|-------------|
| `set-memory health` | Check if shodh-memory is available |
| `set-memory remember --type TYPE [--tags t1,t2]` | Save a memory (reads content from stdin) |
| `set-memory recall "query" [--limit N] [--mode MODE] [--tags t1,t2]` | Semantic search (JSON output) |
| `set-memory list [--type TYPE] [--limit N]` | List memories with optional filters (JSON output) |
| `set-memory status [--json]` | Show config, health, and memory count |
| `set-memory projects` | List all projects with memory counts |

**Forget / Cleanup:**

| Command | Description |
|---------|-------------|
| `set-memory forget <id>` | Delete a single memory by ID |
| `set-memory forget --all --confirm` | Delete ALL memories (requires --confirm) |
| `set-memory forget --older-than <days>` | Delete memories older than N days |
| `set-memory forget --tags <t1,t2>` | Delete memories matching tags |
| `set-memory forget --pattern <regex>` | Delete memories matching regex pattern |

**Introspection:**

| Command | Description |
|---------|-------------|
| `set-memory get <id>` | Get a single memory by ID (JSON output) |
| `set-memory context [topic]` | Condensed summary by category |
| `set-memory brain` | 3-tier memory visualization |

**Export / Import:**

| Command | Description |
|---------|-------------|
| `set-memory export [--output FILE]` | Export all memories to JSON (stdout or file) |
| `set-memory import FILE [--dry-run]` | Import memories from JSON (skip duplicates) |

Export produces a single JSON file with version header, project name, and all records. Import uses UUID-based deduplication — records already present (by ID or `metadata.original_id`) are skipped. Safe for roundtrip: A→export→B→import→B→export→A→import produces no duplicates. Use `--dry-run` to preview without writing.

**Sync (team sharing via git):**

| Command | Description |
|---------|-------------|
| `set-memory sync` | Push + pull in one step |
| `set-memory sync push` | Export and push to git remote |
| `set-memory sync pull [--from user/machine]` | Pull and import from git remote |
| `set-memory sync status` | Show sync state and remote sources |

**Migration:**

| Command | Description |
|---------|-------------|
| `set-memory migrate` | Run pending memory migrations |
| `set-memory migrate --status` | Show migration history |

**Metrics & Reporting:**

| Command | Description |
|---------|-------------|
| `set-memory metrics [--since Nd] [--json]` | Injection quality report (default: last 7 days) |
| `set-memory dashboard [--since Nd]` | Generate HTML dashboard and open in browser |

**Diagnostics:**

| Command | Description |
|---------|-------------|
| `set-memory audit [--threshold N] [--json]` | Report memory health: duplicate clusters, redundancy stats, top clusters |
| `set-memory dedup [--threshold N] [--dry-run] [--interactive]` | Remove duplicate memories, keeping best per cluster with merged tags |

**Maintenance:**

| Command | Description |
|---------|-------------|
| `set-memory health --index` | Check index health (JSON output) |
| `set-memory repair` | Repair index integrity |

**Global options:** `--project NAME` — override auto-detected project name. `--no-migrate` — skip auto-migration.

**Valid types:** `Decision`, `Learning`, `Context`

**Recall modes** (`--mode`): `semantic` (default), `temporal`, `hybrid`, `causal`, `associative`

**Tagging convention:** `change:<name>,phase:<skill>,source:<agent|user>,<topic>`

**Examples:**

```bash
# Save a decision
echo "Use pytest-xdist for parallel testing" \
  | set-memory remember --type Decision --tags source:user,testing,pytest

# Search with enhanced recall
set-memory recall "testing strategy" --limit 5 --mode hybrid

# Search filtered by change
set-memory recall "auth patterns" --tags change:add-auth --mode hybrid

# List only decisions
set-memory list --type Decision --limit 10

# Delete old memories
set-memory forget --older-than 180

# Check status
set-memory status --json

# Add a mandatory rule (deterministic, always injected when topic matches)
set-memory rules add --topics "customer,sql" "Use customer_ro / XYZ123 for customer table"

# List rules
set-memory rules list

# Remove a rule
set-memory rules remove <id>
```

### set-memory-hooks (Legacy)

| Command | Description |
|---------|-------------|
| `set-memory-hooks install` | **Deprecated** — the 5-layer hook system in settings.json handles all memory operations. Use `set-deploy-hooks` instead. |
| `set-memory-hooks check [--json]` | Check whether inline hooks are present in skill files |
| `set-memory-hooks remove [--quiet]` | Remove inline memory hooks from OpenSpec skill files |

**Global option:** `--project NAME` — override auto-detected project name.

> **Note:** `set-project init` now automatically runs `set-memory-hooks remove` to clean up legacy inline hooks.

### /set:memory slash command

Use `/set:memory` inside Claude Code for quick access:

| Subcommand | Description |
|------------|-------------|
| `/set:memory status` | Show health, count, storage path |
| `/set:memory recall <query>` | Semantic search with formatted results |
| `/set:memory remember <content>` | Save a memory (prompts for type and tags) |
| `/set:memory list` | List all memories grouped by type |
| `/set:memory browse` | Summary with recent entries (default) |

---

## Setup

### 1. Install shodh-memory

```bash
pip install 'shodh-memory>=0.1.75,!=0.1.80'
```

### 2. Verify

```bash
set-memory health
set-memory status
```

### Quick Setup Flows

#### A. Fresh project — OpenSpec + memory from scratch

```bash
pip install 'shodh-memory>=0.1.75,!=0.1.80'  # 1. Install memory backend
set-project init                       # 2. Register project + deploy 5-layer hooks to settings.json
set-openspec init                      # 3. Initialize OpenSpec
set-memory health                      # 4. Verify shodh-memory is available
```

#### B. Existing OpenSpec project — enable memory

```bash
pip install 'shodh-memory>=0.1.75,!=0.1.80'  # 1. Install memory backend (if not installed)
set-project init                       # 2. Re-run to deploy 5-layer hooks + auto-remove legacy inline hooks
set-memory health                      # 3. Verify shodh-memory is available
```

#### C. Brownfield project — seed memory from existing OpenSpec artifacts

```bash
pip install 'shodh-memory>=0.1.75,!=0.1.80'  # 1. Install memory backend
set-memory health                      # 2. Verify it works
# 3. Follow docs/memory-seeding-guide.md to extract knowledge from
#    existing proposals, designs, and specs into set-memory
```

See the full [Memory Seeding Guide](memory-seeding-guide.md) for step-by-step instructions.

#### D. After `set-openspec update` — no action needed

The 5-layer hook system lives in `settings.json`, not in SKILL.md files. OpenSpec updates don't affect it:

```bash
set-openspec update                    # Update OpenSpec skills — memory hooks stay active
```

### Graceful degradation

If shodh-memory is not installed:
- `set-memory remember` exits silently (exit 0) — nothing crashes
- `set-memory recall` and `set-memory list` return empty JSON arrays `[]`
- `set-memory status --json` returns `{"available": false, ...}`
- GUI shows "not installed" status
- OpenSpec hooks skip silently

You can install shodh-memory at any time — existing commands and hooks will start working immediately.

---

## Metrics & Reporting

Track how effectively the memory system serves agents across sessions. Metrics are collected automatically by the hook system and stored in a local SQLite database (`~/.local/share/set-core/metrics/metrics.db`).

### TUI Report

```bash
set-memory metrics              # Last 7 days (default)
set-memory metrics --since 30d  # Last 30 days
set-memory metrics --json       # Machine-readable output
```

Shows per-layer injection counts, token usage, relevance distribution, citation rate, dedup hit rate, and top cited memories — all in the terminal.

![TUI metrics report in the terminal](images/memory-metrics-tui.png)

### HTML Dashboard

```bash
set-memory dashboard              # Last 7 days, opens in browser
set-memory dashboard --since 30d  # Last 30 days
```

Generates an interactive HTML dashboard with charts (token burn per day, relevance trend, layer breakdown donut) and a sessions table. Written to `/tmp/set-memory-dashboard.html` and auto-opened in the default browser.

![HTML metrics dashboard in the browser](images/memory-metrics-dashboard.png)

### What's measured

| Metric | Description |
|--------|-------------|
| **Injections** | Total memory injections across all layers (L1-L4) |
| **Tokens burned** | Estimated token count of injected memory context |
| **Relevance distribution** | Strong (>0.7), partial (0.3-0.7), weak (<0.3) matches |
| **Citation rate** | How often agents cite memory in their responses ("From memory:", etc.) |
| **Dedup hit rate** | Injections skipped because the same memory was already in context |
| **Empty injections** | Injections that returned no relevant memories |
| **Per-layer breakdown** | Injection count, avg tokens, avg relevance for L1-L4 |

---

## Benchmarks

**Synthetic (MemoryProbe):** +34% weighted convention compliance when knowledge only exists in memory. **Real-world (CraftBazaar v6):** no measurable delta yet — test infrastructure gaps mask potential benefits.

See [Research: Benchmark Results](research/benchmark-results.md) for full methodology, per-trap analysis, and evolution across 10 runs.

---

## Architecture

<details>
<summary>Technical details (click to expand)</summary>

### Layer diagram

```
┌────────────────────────────────────────────────────────────┐
│                      Agent Session                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  5-Layer Hook System (settings.json)                  │  │
│  │  L1 SessionStart    → warmstart + discovery           │  │
│  │  L2 UserPromptSubmit → topic recall                   │  │
│  │  L3 PreToolUse[Bash] → hot-topic recall               │  │
│  │  L4 PostToolUseFailure[Bash] → error recall + promote │  │
│  │  L5 Stop             → haiku extract + design choices │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                          │                                   │
│  ┌──────────────┐       │       ┌──────────────────────┐   │
│  │  CLAUDE.md   │       │       │  .claude/            │   │
│  │  (persistent │       │       │  hot-topics.json     │   │
│  │   memory)    │       │       │  (L1 writes, L3/L4   │   │
│  └──────────────┘       │       │   reads/updates)     │   │
│                          │       └──────────────────────┘   │
│                          ▼                                   │
│                   ┌────────────┐                            │
│                   │ set-memory  │                            │
│                   │ (CLI)      │                            │
│                   └─────┬──────┘                            │
│                         │                                    │
│                   ┌─────▼──────────────────┐               │
│                   │   shodh-memory         │               │
│                   │   (Python library)     │               │
│                   └─────┬──────────────────┘               │
│                         │                                    │
│                   ┌─────▼──────────────────┐               │
│                   │   RocksDB              │               │
│                   │   Per-project storage  │               │
│                   └────────────────────────┘               │
└────────────────────────────────────────────────────────────┘
```

### Key design choices

- **Hook-driven, not skill-driven**: All memory operations happen via Claude Code hooks. Skills contain no inline memory instructions.
- **Per-project isolation**: Each project gets its own RocksDB database. Worktrees of the same repo share memory (detected via `git worktree list`).
- **File locking**: Uses `/tmp/set-memory-<project>.lock` to prevent concurrent RocksDB access from multiple agents.
- **Semantic search**: `recall` uses shodh-memory's built-in embedding and similarity search.
- **Bash-only for L3/L4**: PreToolUse and PostToolUseFailure only match Bash due to CLI latency (~150ms). Future MCP integration could extend to Edit/Read/Write.
- **No hard dependency**: Everything degrades gracefully. Memory is an enhancement, not a requirement.

</details>

---

*See also: [Getting Started](getting-started.md) · [Configuration](configuration.md) · [MCP Server](mcp-server.md) · [CLI Reference](cli-reference.md)*
