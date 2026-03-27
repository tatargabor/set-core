[< Back to README](../README.md)

# Orchestration Guide

`set-orchestrate` is an autonomous multi-change execution engine. It reads a specification document, decomposes it into independent changes using an LLM, dispatches each to its own worktree with a Ralph loop, and monitors everything to completion — merging results back to main as they finish.

---

## Quick Start

```bash
# 1. Write your spec (any format — markdown, design doc, feature list)
cat docs/v3-release.md

# 2. Generate a plan
set-orchestrate --spec docs/v3-release.md plan

# 3. Review the plan
set-orchestrate plan --show

# 4. Execute
set-orchestrate start

# 5. Monitor progress
set-orchestrate status
```

That's it. The orchestrator creates worktrees, starts Ralph loops, monitors progress, merges completed work, and stops when everything is done.

---

## Example Walkthrough

Suppose you have a project with this spec document (`docs/v3-release.md`):

```markdown
# v3 Release Plan

## Authentication
- Add JWT-based auth middleware
- Add user roles (admin, editor, viewer)

## API
- Add REST endpoints for user management
- Add rate limiting middleware

## Infrastructure
- Add structured logging with correlation IDs
- Update CI pipeline for the new auth tests
```

### Step 1: Plan

```bash
set-orchestrate --spec docs/v3-release.md plan
```

The orchestrator sends your spec to Claude, which decomposes it into sized, dependency-ordered changes:

```
[INFO] Reading input (spec): docs/v3-release.md
[INFO] Directives: {"max_parallel":2,"merge_policy":"checkpoint",...}
[INFO] Planning 6 changes from spec...
[INFO] Plan saved to orchestration-plan.json
```

### Step 2: Review

```bash
set-orchestrate plan --show
```

```
═══ Orchestration Plan ═══

  add-jwt-auth [M] — Add JWT-based authentication middleware...
    depends_on: (none)
  add-user-roles [M] — Add user roles (admin, editor, viewer)...
    depends_on: add-jwt-auth
  add-user-api [M] — REST endpoints for user management...
    depends_on: add-jwt-auth
  add-rate-limiting [S] — Rate limiting middleware...
    depends_on: (none)
  add-structured-logging [S] — Structured logging with correlation IDs...
    depends_on: (none)
  update-ci-auth [S] — Update CI pipeline for auth tests...
    depends_on: add-jwt-auth

Dependency order:
  1. add-jwt-auth
  2. add-rate-limiting
  3. add-structured-logging
  4. add-user-roles
  5. add-user-api
  6. update-ci-auth
```

The orchestrator respects dependencies — `add-user-roles` won't start until `add-jwt-auth` is merged.

### Step 3: Execute

```bash
set-orchestrate start
```

The orchestrator:
1. Creates worktrees for changes that have no unmet dependencies (up to `max_parallel`)
2. Runs `opsx:ff` in each worktree to generate OpenSpec artifacts
3. Starts a Ralph loop in each worktree to implement the change
4. Polls every 30 seconds for completion
5. When a change finishes, merges it to main and dispatches the next available change
6. Repeats until all changes are done

```
[INFO] Dispatching: add-jwt-auth (M)
[INFO] Dispatching: add-rate-limiting (S)
[INFO]   → Worktree created, Ralph loop started
[INFO]   → Worktree created, Ralph loop started
[INFO] Monitoring 2 active changes...
...
[INFO] add-rate-limiting completed → merging
[INFO] Merge successful: add-rate-limiting
[INFO] Dispatching: add-structured-logging (S)
...
[INFO] add-jwt-auth completed → merging
[INFO] Merge successful: add-jwt-auth
[INFO] Dispatching: add-user-roles (M)
[INFO] Dispatching: add-user-api (M)
```

### Step 4: Monitor

While the orchestrator runs, check status anytime from another terminal:

```bash
set-orchestrate status
```

```
Orchestration Status: running
  Elapsed: 1h23m | Changes: 4/6 done | Active: 2

  add-jwt-auth        ✅ done     (merged)
  add-rate-limiting    ✅ done     (merged)
  add-structured-log   ✅ done     (merged)
  add-user-roles       🔄 running  (ralph: iteration 3)
  add-user-api         🔄 running  (ralph: iteration 2)
  update-ci-auth       ⏳ waiting  (blocked by: add-jwt-auth ✅)
```

---

## Input Modes

### Spec mode (recommended)

Pass any document — the orchestrator uses Claude to extract actionable changes:

```bash
set-orchestrate --spec docs/release-plan.md plan
set-orchestrate --spec docs/design-doc.md plan
```

For large specs, use `--phase` to focus on a subset:

```bash
set-orchestrate --spec docs/v3-release.md --phase 1 plan        # plan phase 1
set-orchestrate --spec docs/v3-release.md --phase "Security" plan # plan by name
```

### Brief mode (legacy)

Create `openspec/project-brief.md` with a `### Next` section:

```markdown
### Next
- Add JWT authentication
- Add rate limiting
- Update CI pipeline
```

```bash
set-orchestrate plan    # auto-detects project-brief.md
```

---

## Configuration

### In-document directives

Add an `## Orchestrator Directives` section to your spec:

```markdown
## Orchestrator Directives
- max_parallel: 3
- merge_policy: eager
- test_command: npm test
- auto_replan: true
```

### Config file

Create `.claude/orchestration.yaml`:

```yaml
max_parallel: 3
merge_policy: checkpoint    # eager | checkpoint | manual
checkpoint_every: 3         # merge-checkpoint after every N changes
test_command: npm test       # run after each merge
smoke_command: pnpm test:smoke  # post-merge smoke test
smoke_timeout: 120              # seconds
post_merge_command: pnpm db:generate  # custom command after merge (e.g., Prisma generate)
auto_replan: true            # auto-advance to next phase
pause_on_exit: false         # pause running changes on Ctrl+C
```

### CLI flags

CLI flags override config and directives:

```bash
set-orchestrate --max-parallel 4 --time-limit 2h start
```

### Precedence

Settings are resolved in order (highest wins):

1. CLI flags (`--max-parallel`, `--time-limit`)
2. Config file (`.claude/orchestration.yaml`)
3. In-document directives (`## Orchestrator Directives`)
4. Defaults

### Full Directive Reference

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_parallel` | int | `2` | Max concurrent changes |
| `default_model` | string | `opus` | Default LLM model for changes |
| `time_limit` | duration | `5h` | Stop after duration (`2h`, `4h30m`, `none`) |
| `checkpoint_interval` | int | `5` | Merge-checkpoint every N completed changes |
| `test_command` | string | `""` | Test command run in worktree before merge |
| `build_command` | string | `""` | Build command run in worktree before merge |
| `smoke_command` | string | `""` | Post-merge smoke test command |
| `smoke_timeout` | int | `120` | Smoke test timeout in seconds |
| `smoke_blocking` | bool | `true` | Whether smoke failure blocks the pipeline |
| `review_model` | string | `""` | Model for code review gate (auto-escalates on failure) |
| `model_routing` | string | `off` | `off` or `complexity` — auto-route S-complexity non-feature changes to sonnet |
| `plan_approval` | bool | `false` | Require `set-orchestrate approve` after plan generation |
| `context_pruning` | bool | `true` | Remove orchestrator commands from agent worktrees |
| `max_tokens_per_change` | int | `0` | Per-change token budget (0 = complexity defaults: S=500K, M=2M, L=5M, XL=10M) |
| `watchdog_timeout` | int | `""` | Seconds before watchdog considers a change stuck |
| `watchdog_loop_threshold` | int | `""` | Consecutive identical hashes before loop detection |
| `require_full_coverage` | bool | `false` | Block plan if any digest requirements are unassigned (digest mode only) |
| `events_log` | string | `""` | Custom path for events JSONL log |
| `events_max_size` | int | `1048576` | Events log rotation threshold in bytes (1MB default) |

#### Hooks

| Directive | Description |
|-----------|-------------|
| `hook_pre_dispatch` | Script run before dispatching a change (non-zero blocks) |
| `hook_post_verify` | Script run after verification passes (non-zero blocks merge) |
| `hook_pre_merge` | Script run before merge (non-zero blocks) |
| `hook_post_merge` | Script run after successful merge (non-blocking) |
| `hook_on_fail` | Script run when a change transitions to `failed` |

Hook scripts receive `(change_name, status, worktree_path)` as arguments. Non-zero exit blocks the transition (except `post_merge` and `on_fail` which are non-blocking).

---

## Merge Policies

| Policy | Behavior |
|--------|----------|
| `eager` | Queue changes for sequential merge as they complete (one at a time) |
| `checkpoint` | Batch merges every N completed changes, wait for approval |
| `manual` | Queue merges, only flush on `set-orchestrate approve --merge` |

All merge policies use a sequential queue — only one merge runs at a time. Each merge runs the full post-merge pipeline (dep install, custom command, scope verify, build verify, smoke test) before the next merge starts.

---

## Pause, Resume, Replan

```bash
# Pause one change
set-orchestrate pause add-user-roles

# Pause everything
set-orchestrate pause --all

# Resume
set-orchestrate resume add-user-roles
set-orchestrate resume --all

# Update your spec, then re-plan (preserves completed work)
set-orchestrate replan
```

---

## Verification Gates

Changes go through pre-merge and post-merge quality gates.

### Pre-merge gate (worktree)

Runs inside the worktree before merge:

1. **Build** — `tsc --noEmit` (or configured build command)
2. **Unit tests** — `vitest run` (or configured test command)
3. **Code review** — optional LLM review (`review_before_merge: true`)

If any step fails, the Ralph loop gets the error output and retries (up to `max_verify_retries`, default 2).

### Post-merge pipeline (main repo)

After a successful merge to main, the orchestrator runs a sequential pipeline. Only one merge runs at a time.

1. **Base build cache invalidation** — force rebuild on next verify
2. **Dependency install** — if `package.json` changed
3. **Custom command** — `post_merge_command` if configured (e.g., `pnpm db:generate` for Prisma)
4. **Scope verification** — checks `git diff HEAD~1` for non-artifact files (warns if only openspec files merged)
5. **Build verification** — runs `test_command` on main to ensure the build still passes
6. **Smoke test** — runs `smoke_command` if configured; on failure, an LLM agent (sonnet, 20 turns) attempts to fix the code or tests on main
7. **Memory logging** — records merge result
8. **Worktree cleanup** — removes the merged worktree
9. **Change archive** — archives the completed change

**Config:**
```yaml
smoke_command: pnpm test:smoke     # the command to run
smoke_timeout: 120                 # seconds
post_merge_command: pnpm db:generate  # project-specific command after dep install
```

**Smoke failure handling:** If smoke fails, the orchestrator spawns a sonnet agent on the main worktree with the failure output and lets it fix the issue (code or test). If the fix succeeds and smoke passes on re-run, the pipeline continues. If the fix fails, a critical notification is sent and the pipeline continues (no revert).

**Scope verification:** Detects "merged but no implementation" — when a change only committed openspec artifacts without actual code. This is non-blocking (warning only).

---

## Safety

- **Time limit**: default 5 hours. Override with `--time-limit 2h` or `--time-limit none`
- **Crash recovery**: state is persisted to `orchestration-state.json`. Run `set-orchestrate start` again to resume
- **Ctrl+C**: saves state and optionally pauses running changes (`pause_on_exit: true`)
- **Post-merge verification**: if `test_command` or `smoke_command` is set, they run after each merge. Failures attempt LLM auto-fix; if auto-fix fails, a critical notification is sent (pipeline continues)

---

## Events

The orchestrator emits structured events to `orchestration-events.jsonl` for audit trails and observability.

### Event Format

```json
{"ts":"2026-03-07T14:30:00+01:00","type":"STATE_CHANGE","change":"add-auth","data":{"from":"running","to":"done"}}
```

Each event has: `ts` (ISO timestamp), `type`, optional `change` (change name), and `data` (type-specific payload).

### Event Types

| Type | Emitted By | Data Fields | Description |
|------|-----------|-------------|-------------|
| `STATE_CHANGE` | `update_change_field` | `from`, `to` | Change status transition |
| `DISPATCH` | `dispatch_change` | `scope` | Change dispatched to worktree |
| `TOKENS` | `update_change_field` | `delta`, `total` | Token usage update (>10K delta) |
| `MERGE_ATTEMPT` | `merge_change` | — | Merge started |
| `VERIFY_GATE` | `handle_change_done` | `test`, `build`, `review`, `smoke` | Verification results |
| `VERIFY_RULE` | `evaluate_verification_rules` | `rule`, `severity`, `check` | Project knowledge rule result |
| `REPLAN` | `auto_replan_cycle` | `cycle`, `completed`, `novel_count` | Replan cycle |
| `CHECKPOINT` | `trigger_checkpoint` | `reason` | Merge checkpoint triggered |
| `ERROR` | various | `error` | Error condition |
| `HOOK_BLOCKED` | `run_hook` | `hook`, `reason` | Lifecycle hook blocked transition |
| `WATCHDOG_HEARTBEAT` | `watchdog_heartbeat` | `active`, `stalled`, `stuck` | Per-poll-cycle health |
| `WATCHDOG_WARN` | `_watchdog_escalate` | `level` | Watchdog warning (level 1) |
| `WATCHDOG_RESUME` | `_watchdog_escalate` | `level` | Watchdog resume attempt (level 2) |
| `WATCHDOG_KILL` | `_watchdog_escalate` | `level` | Watchdog kill (level 3) |
| `WATCHDOG_FAILED` | `_watchdog_escalate` | `level` | Watchdog failure (level 4+) |
| `WATCHDOG_TOKEN_BUDGET` | `_watchdog_check_token_budget` | `tokens_used`, `limit`, `pct`, `action` | Token budget enforcement |
| `WATCHDOG_SALVAGE` | `_watchdog_salvage_partial_work` | `files`, `patch` | Partial work salvaged before failure |
| `SENTINEL_RESTART` | `/set:sentinel` skill | `exit_code`, `runtime`, `reason` | Sentinel restarted orchestrator |
| `SENTINEL_FAILED` | `/set:sentinel` skill | `rapid_crashes` | Sentinel gave up |
| `STATE_RECONSTRUCTED` | `reconstruct_state_from_events` | `event_count`, `status` | State rebuilt from events |

### Querying Events

```bash
# Show all events (table format)
set-orchestrate events

# Filter by type
set-orchestrate events --type STATE_CHANGE

# Filter by change
set-orchestrate events --change add-auth

# Recent events
set-orchestrate events --last 20

# Since a timestamp
set-orchestrate events --since 2026-03-07T14:00:00

# JSON output for scripting
set-orchestrate events --type ERROR --json
```

### Log Rotation

The events log rotates when it exceeds `events_max_size` (default 1MB). The last 3 archives are kept, named with timestamps (e.g., `orchestration-events-20260307143000.jsonl`).

## Files

| File | Purpose |
|------|---------|
| `orchestration-plan.json` | LLM-generated change plan with dependency graph |
| `orchestration-state.json` | Runtime state (change statuses, merge queue) |
| `orchestration-events.jsonl` | Structured event log (JSONL format) |
| `orchestration-summary.md` | Human-readable summary (generated on completion) |
| `.claude/orchestration.yaml` | Optional configuration |
| `.claude/orchestration.log` | Debug log (auto-rotated at 100KB) |
| `project-knowledge.yaml` | Optional project knowledge for smarter orchestration |
| `design-snapshot.md` | Combined Figma design data (generated by `set-figma-fetch`) |

## Design Integration

The orchestrator reads `design-snapshot.md` from the project root — no runtime Figma MCP calls are made during orchestration.

**Workflow:**

1. Run `set-figma-fetch docs/` to scan markdown files for Figma URLs and fetch design data
2. Commit the `figma-raw/` directories and `design-snapshot.md` to the repo
3. The planner, dispatcher, verifier, and engine all read `design-snapshot.md` from CWD automatically
4. Re-run `set-figma-fetch --force docs/` when designs change in Figma

**What gets fetched:**

| File type | Data captured |
|-----------|---------------|
| Design files | Metadata, design tokens (variable defs), component hierarchy, screenshots |
| Make files | Component hierarchy, all source files (TSX/CSS/config), Tailwind tokens extracted |

Raw MCP responses are saved in `<docs-dir>/figma-raw/<file-key>/` so `--reprocess` can re-assemble without re-fetching.

---

## Troubleshooting

### Stuck orchestrator

The **watchdog** monitors each change for progress. If a change's `loop-state.json` stops updating and the Ralph PID is dead, the watchdog escalates through levels:

1. **Warn** — log warning, emit `WATCHDOG_WARN` event
2. **Resume** — attempt to resume the stalled change
3. **Kill** — terminate the process, attempt resume
4. **Fail** — mark change as failed, salvage partial work as `partial-diff.patch`

The **sentinel** independently monitors `orchestration-events.jsonl` mtime. If no events are emitted for `sentinel_stuck_timeout` (default 180s), the sentinel kills and restarts the entire orchestrator.

### Merge-blocked changes

When a merge conflict can't be auto-resolved (LLM resolver output is empty), the change enters `merge-blocked` status. The orchestrator continues with other changes.

To resolve:
1. Manually resolve conflicts in the change's worktree
2. Run `set-orchestrate approve <change-name>` to retry merge

### Token budget exceeded

The watchdog enforces per-change token budgets based on complexity:

| Complexity | Default Budget |
|------------|---------------|
| S | 500K tokens |
| M | 2M tokens |
| L | 5M tokens |
| XL | 10M tokens |

Override with `max_tokens_per_change` directive. At 80% the watchdog warns, at 100% it pauses the change, at 120% it fails it.

### State reconstruction

If `orchestration-state.json` becomes inconsistent (e.g., running changes with dead PIDs, state older than events), the sentinel automatically reconstructs state from `orchestration-events.jsonl` on startup.

Manual reconstruction is also available via the `reconstruct_state_from_events()` function in `state.sh`.

### Plan approval gate

With `plan_approval: true`, the orchestrator enters `plan_review` status after generating the plan. Review with `set-orchestrate plan --show`, then `set-orchestrate approve` to start dispatch.

## CLI Reference

```
set-orchestrate [options] <command>

Options:
  --spec <path>          Specification document
  --brief <path>         Structured brief (legacy)
  --phase <hint>         Phase filter (number or text)
  --max-parallel <N>     Max concurrent changes
  --time-limit <dur>     Stop after duration (default: 5h)

Commands:
  plan [--show]          Generate or show plan
  start                  Execute the plan
  status                 Show progress
  events [filters]       Query event log (--type, --change, --since, --last, --json)
  pause <name|--all>     Pause changes
  resume <name|--all>    Resume changes
  replan                 Re-plan from updated spec
  approve [name|--merge] Approve checkpoint / flush merge queue / unblock change
```

---

## Review Learnings

The orchestrator accumulates review findings across changes and runs, building a persistent checklist that prevents recurring mistakes.

### How it works

1. **During merge** — after a change merges, `_persist_change_review_learnings()` extracts CRITICAL/HIGH patterns from `review-findings.jsonl`, classifies them via Sonnet as `template` (cross-project) or `project` scope, and writes to the appropriate JSONL
2. **During dispatch** — `review_learnings_checklist()` reads from 3 sources and injects into the agent's input.md as `## Review Learnings Checklist`
3. **During review** — the verify gate blocks if checklist items are violated

### Three sources (priority order)

| Source | Path | Scope | Tag |
|--------|------|-------|-----|
| Project JSONL | `{project}/set/orchestration/review-learnings.jsonl` | This project only | `[project, seen Nx]` |
| Template JSONL | `~/.config/set-core/review-learnings/{profile}.jsonl` | All projects of same type | `[template, seen Nx]` |
| Static baseline | `modules/{type}/review_baseline.md` | Hardcoded per profile | `[baseline]` |

### Seeding from past runs

New installations or new profile types start with an empty template JSONL. To seed it from existing E2E run findings:

```bash
# Dry run — see what patterns would be extracted
python scripts/migrate-review-learnings.py --dry-run

# Run migration (auto-discovers all runs under ~/.local/share/set-core/e2e-runs/)
python scripts/migrate-review-learnings.py

# Specify profile name (when not running from a project directory)
python scripts/migrate-review-learnings.py --profile web

# Migrate specific runs only
python scripts/migrate-review-learnings.py --run-dir ~/.local/share/set-core/e2e-runs/craftbrew-run8
```

The script reads `review-findings.jsonl` from each run, extracts CRITICAL/HIGH issues, deduplicates across runs, and writes to `~/.config/set-core/review-learnings/{profile}.jsonl`.

After migration, verify the checklist output:
```bash
python -c "
import sys; sys.path.insert(0, 'lib')
from set_orch.profile_loader import load_profile
profile = load_profile()
print(profile.review_learnings_checklist('.'))
"
```

### Storage details

- Both JSONLs are capped at 50 entries (oldest pruned by `last_seen`)
- Template JSONL uses `flock` for concurrent write safety
- Patterns are deduplicated by normalized text (first 60 chars, case-insensitive)
- Each entry tracks `count`, `last_seen`, and `source_changes` for prioritization

---

*See also: [Sentinel](sentinel.md) · [Configuration](configuration.md) · [Ralph Loop](ralph.md) · [Architecture](architecture.md)*
