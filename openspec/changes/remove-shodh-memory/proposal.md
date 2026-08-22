## Why

set-core's memory subsystem did not merely fail to help — it injected false claims about
the user into unrelated sessions, and it persisted confidential content while doing so.

Measured 2026-08-21 over 21 days of session transcripts (4958 files under
`~/.claude/projects`): **187 memory lines reached a session, and 168 of them (89.8 %) were
`User frustrated` records**. The detector fires on exclamation marks, so `szuper!!!` and
`pont igy akartam!!!` — both the user being pleased — were stored and replayed as anger.
Their payloads were not knowledge at all: raw `<task-notification>` blocks,
`<cross-session-message>` bodies, other agents' system prompts, and meeting-transcript
fragments captured verbatim from whatever prompt was in flight. **Exactly one line in 187
was a reusable project fact.**

Three further defects, each measured and registered:

- The knowledge graph has been **0 nodes / 0 edges through 56 → 7864 memories**, so
  `--mode causal` and `--mode associative` — which the explore and apply skills pass — are
  aliases of `--mode semantic` (B-52).
- `export` returned `count: 0` while the daemon held the RocksDB lock, and exited 0. There
  has never been a working backup (B-50).
- `list --limit N` returns `[]` for N ≥ 58, so the store is unauditable beyond 57 records
  (B-51).

And the decisive comparison (B-54): in one project both memory systems ran side by side.
Every remembered fact a session actually *acted on* — a named alert channel, a
fetch-before-allocating-an-id rule, a pending deploy item — traces to a hand-written file in
Claude Code's **native** memory directory. The same three facts appear **0 times** in the
120 shodh injection blocks from that same project.

Why now: the harm is active, and the confidentiality carrier is the one
[CLAUDE.md](../../../CLAUDE.md) names explicitly — session-end extraction persisting
consumer and personal content. That is not a defect to schedule; it is one to stop.

## What Changes

**BREAKING** — the `set-memory` CLI, the `set-memoryd` daemon, the memory MCP tools and the
memory hooks are removed. Nothing replaces their interface; the native file memory is not a
drop-in and is not addressed by a command.

- **BREAKING** Remove `bin/set-memory`, `bin/set-memoryd`, `bin/set-memory-hooks`,
  `bin/set-hook-memory`, and the five legacy `set-hook-memory-{warmstart,recall,pretool,
  posttool,save}` scripts.
- **BREAKING** Remove `lib/set_memoryd/`, `lib/memory/`, `lib/set_hooks/`,
  `lib/frustration.py`.
- **BREAKING** Remove the **27** memory MCP tools from `mcp-server/set_mcp_server.py`,
  leaving **7**: `list_worktrees`, `get_ralph_status`, `get_worktree_tasks`,
  `get_team_status`, `get_activity`, `send_message`, `get_inbox`. (`run_command` is an
  internal helper, not a registered tool — an earlier draft counted it as an eighth.) The 27 are `remember`,
  `recall`, `recall_by_date`, `proactive_context`, `forget`, `forget_by_tags`,
  `list_memories`, `get_memory`, `context_summary`, `brain`, `memory_stats`,
  `memory_health`, `audit`, `cleanup`, `dedup`, `verify_index`, `consolidation_report`,
  `graph_stats`, `sync`, `sync_push`, `sync_pull`, `sync_status`, `export_memories`,
  `import_memories`, and the todo trio `add_todo`, `list_todos`, `complete_todo` — the todos
  are shodh-backed and go with it. An earlier draft of this bullet said eleven; the number
  was written from the tools that came to mind rather than from counting the file.
- **BREAKING** Remove `/set:memory` and `/set:todo`, and the `set-memory` references in
  `/set:help`, `skills/set/decompose/SKILL.md` and `rules/capability-guide.md`.
- **Root cause:** `bin/set-deploy-hooks` stops emitting the nine memory hooks, and its
  existing `--no-memory` strip becomes unconditional, so any project still carrying them is
  cleaned by its next `set-project init`. Without this the next init re-installs all nine
  into all 35 projects.
- Rewrite CLAUDE.md's **Persistent Memory** section. It currently instructs every session to
  scan for an injection that no longer arrives, so the rule book is itself wrong.
- Retarget the documentation. `docs/research/shodh-memory-audit.md` is **kept** as the
  historical record of how this was found.
- Record what the native layer does and does not give, so the loss is stated rather than
  discovered later.

Already done outside this change, referenced so it is not re-planned: `259ab007` unbound all
nine hooks in set-core; 35 other projects were stripped with `set-deploy-hooks --no-memory`
(29 pathspec-limited commits, 6 untracked, every project's own hooks verified preserved);
both daemons stopped; the store archived and verified — 3.3 GB → 345 MB zstd, 81 346
entries, plus a 7885-record JSON export and the one open todo, at
`~/.local/share/set-core/memory-archive-20260821/`.

## Capabilities

### New Capabilities

- `native-memory-layer`: what set-core's memory IS after this change — the per-repository
  Markdown directory Claude Code owns, its `MEMORY.md` index and the **first 200 lines /
  25 KB** that load at session start, what the framework may and may not write into it, and
  the confidentiality rule that survives the removal. It also states, as requirements, the
  capabilities deliberately **not** replaced: semantic search, tags, temporal queries,
  full-text search, cross-device sync, version history, and automatic session-end
  extraction.

### Modified Capabilities

- `hook-auto-install`: the auto-installed hook set no longer contains memory hooks, and the
  deployer strips any it finds. This is the requirement change that keeps the other 35
  projects clean.
- `hook-config-downgrade`: the downgrade path loses its memory-hook branches.
- `mcp-consolidation`: the MCP tool surface loses 27 of its 34 tools; the consolidation contract must
  state the smaller surface rather than describe tools that no longer exist.
- `help-command`: `/set:help` no longer advertises memory or todo commands.
- `project-health-scan`: **the polarity inverts.** Today `set-audit` reports ❌ when
  `set-hook-memory` is ABSENT and tells you to run `set-deploy-hooks` — so after this change
  the audit would instruct all 35 projects to reinstall exactly what was removed. Their
  presence becomes the finding.

### Removed Capabilities

Forty-five capability specs exist **because** shodh existed; with it gone they describe
nothing. They are removed wholesale rather than each carrying a `## REMOVED Requirements`
delta, because a delta per spec would restate roughly 250 requirements to say one thing.
This is a deliberate, stated deviation from the per-spec delta convention — recorded here so
it is reviewable rather than silent:

`auto-memory-hooks-deploy`, `shodh-cli-upgrade`, `shodh-api-parity`, `memory-cli`, `mcp-memory-tools`, `memory-todo`,
`memory-dedup`, `memory-concurrency`, `memory-branch-tags`, `memory-migrations`,
`memory-skill`, `memory-type-mapping`, `memory-rules`, `memory-hooks-cli`,
`memory-tui-dashboard`, `memory-phase-tags`, `memory-save-hook`, `orchestrator-memory`,
`developer-memory-docs`, `skill-memory-hooks`, `skill-hook-automation`,
`unified-memory-hook`, `hook-driven-memory`, `session-warmstart`, `wt-memory-integration`,
`error-recovery-recall`, `rocksdb-log-cleanup`, `raw-transcript-filter`,
`utf8-safe-content-handling`, `agent-self-reflection`, `hot-topic-recall`,
`subagent-context-injection`, `explore-memory`, `smart-memory-recall`,
`stop-hook-extraction`, `stop-hook-memory-reminder`, `posttool-memory-surfacing`,
`ambient-memory`, `frustration-detection`, `turn-checkpoint-save`,
`proactive-hybrid-fallback`, `save-hook-staging`, `midflow-memory`, `memory-heuristic-guard`,
`memory-context-id`.

Sixteen further specs reference `set-memory` without owning it. Six of them are the
Modified Capabilities above, because the framework behaviour they describe really does
change. The remaining ten — `benchmark-testing`, `benchmark-metrics-integration`,
`context-preservation`, `feature-worker`, `gui-logging`, `init-error-handling`,
`loop-startup-info`, `metrics-reporting`, `modular-source-structure`, `worktree-tools` —
keep every requirement; only the mention is corrected, as a task.

The counts are the measured ones: 57 specs reference shodh, 45 are removed, 15 reference it
without owning it, and 3 of the 44 (`midflow-memory`, `memory-heuristic-guard`,
`memory-context-id`) do not match the reference grep at all but exist only to describe the
subsystem. An earlier draft of this paragraph said thirty-six and twenty-one; both were
written from the shape of the list rather than from counting it.

## Impact

**Code surface, measured:** 63 live files — `lib/` 30, `tests/` 17, `bin/` 9, `.claude/` 5,
`mcp-server/` 1, `templates/` 1 — plus `install.sh` and `README.md`. Documentation: 70 files.

**Two entangled capabilities, both measured, neither dropped silently:**

- `load_matching_rules()` (`lib/set_hooks/memory_ops.py:129`) reads `.claude/rules.yaml` and
  is **entirely shodh-independent** — but **zero** projects on this machine have a
  `rules.yaml`. It goes with the hook. Stated here rather than lost in a deletion.
- The GTD todo system **is** shodh-backed. One open todo exists (2026-04-20) and is already
  saved to the archive. This change drops todos rather than porting them; if they come back
  it is as its own change on its own substrate.

**Dependencies:** `shodh-memory` is installed twice on this machine — 0.1.81 under
miniconda, 0.1.90 under linuxbrew. Both are uninstalled by this change.

**Out of scope, deliberately:**

- **Adopting a replacement.** Researched 2026-08-21: Basic Memory is the only candidate
  matching the criterion this failure argues for — plain text you own, no daemon, no LLM in
  the loop, retrieval reproducible by hand. Nothing is adopted until the native layer is
  *measured* insufficient. Choosing a replacement now would be measuring it against a system
  that delivered one useful line in 187.
- **Deleting the archived store.** It holds confidential content and is 345 MB; removing it
  is a separate, explicitly approved step.

**Known constraint to carry forward:** one project's `MEMORY.md` is already
**123 lines / 20 550 bytes**, against a 200-line / 25 KB startup cut. The native layer's size
limit is a near-term concern, not a theoretical one.
