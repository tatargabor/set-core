# Reference

## CLI Reference

### set-orchestrate

The main orchestration command.

```
set-orchestrate [global options] <command> [command options]
```

#### Global Options

| Option | Description |
|--------|-------------|
| `--spec <path>` | Specification file or directory |
| `--brief <path>` | Brief file (legacy) |
| `--phase <hint>` | Phase filter (with --spec) |
| `--max-parallel <N>` | Max parallel override |
| `--time-limit <dur>` | Time limit (e.g., "4h", "2h30m", "none") |

#### Commands

| Command | Description |
|---------|-------------|
| `plan [--show]` | Generate plan or display existing |
| `start` | Start plan execution |
| `status` | Display current status |
| `pause <name\|--all>` | Suspend a change or all |
| `resume <name\|--all>` | Resume a change or all |
| `replan` | Replan from updated spec |
| `approve [--merge]` | Checkpoint approval |
| `digest --spec <path>` | Generate structured digest |
| `coverage` | Requirement coverage report |
| `specs [list\|show\|archive]` | Spec document management |
| `events [opts]` | Event log query |
| `tui` | Start terminal dashboard |
| `self-test` | Run internal tests |

### set-new / set-merge / set-loop

| Command | Description |
|---------|-------------|
| `set-new <name>` | Create new worktree and branch |
| `set-merge <name> [--llm-resolve]` | Merge worktree to main |
| `set-loop start [opts]` | Start Ralph loop |
| `set-loop status` | Query loop status |

## Change State Machine

Changes move through the following states during their lifecycle:

![The complete change state machine](diagrams/rendered/09-change-lifecycle.png){width=95%}

### States

| State | Description |
|-------|-------------|
| `pending` | Waiting for dispatch (dependencies not met) |
| `dispatched` | Worktree created, Ralph loop starting |
| `running` | Ralph loop active, development in progress |
| `verifying` | Verify pipeline running (test → review → verify → smoke) |
| `verify-failed` | Verify gate failed, retry pending |
| `stalled` | Watchdog detected the agent is stuck |
| `paused` | Manually suspended |
| `waiting:budget` | Waiting due to token budget limit |
| `budget_exceeded` | Token budget exceeded |
| `merge_queue` | Verify successful, waiting for merge |
| `merging` | Merge in progress |
| `merge_blocked` | Merge conflict, could not resolve |
| `merged` | Successfully merged to main branch |
| `smoking` | Post-merge smoke test running |
| `smoke_failed` | Smoke test failed |
| `smoke_blocked` | Smoke fix retry limit reached |
| `completed` | All gates successfully passed |
| `failed` | Permanently failed (retry limit reached) |
| `skipped` | Skipped (dependency failed) |

### Key State Transitions

```
pending → dispatched → running → verifying
  ↑                      ↕          ↓
  │                   stalled    merge_queue → merging → merged → completed
  │                      ↓          ↑
  │                   failed    verify-failed (→ running retry)
  │                                 ↓
  └── skipped (dependency failed)  failed (retry exhausted)
```

## Directive Table

Directives control system behavior. The tables below show all available settings by category. Most projects start with default values and only set the test commands (`test_command`, `smoke_command`) and parallelism level (`max_parallel`). The remaining directives are for fine-tuning, which is typically needed only after the first few runs.

### Execution

These directives define the basic parameters of execution: how many agents work simultaneously, how merging happens, and how long the system can run.

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_parallel` | number | 3 | Max parallel worktrees |
| `merge_policy` | enum | checkpoint | eager / checkpoint / manual |
| `checkpoint_every` | number | 3 | Checkpoint merge count |
| `time_limit` | string | 5h | Active time limit |
| `pause_on_exit` | bool | false | Pause when orchestrator stops |
| `context_pruning` | bool | true | Context window optimization |
| `model_routing` | string | off | Model routing strategy |

### Models

There are three model tiers: opus for heavy work (implementation), sonnet for faster tasks (review, simple changes), haiku for summarization. Model routing can automatically choose based on change complexity.

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `default_model` | string | opus | Implementation model |
| `review_model` | string | sonnet | Review model |
| `summarize_model` | string | haiku | Summarization model |

### Testing

Testing directives configure the quality gates. `test_command` is the most important: if empty, the test gate is skipped entirely. Smoke and E2E tests are optional but strongly recommended for production runs — smoke catches build errors, E2E catches functional regressions.

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `test_command` | string | "" | Test command |
| `test_timeout` | number | 300 | Test timeout (seconds) |
| `smoke_command` | string | "" | Smoke test command |
| `smoke_timeout` | number | 120 | Smoke timeout (seconds) |
| `smoke_blocking` | bool | true | Does smoke fail block |
| `smoke_fix_token_budget` | number | 500K | Smoke fix token limit |
| `smoke_fix_max_turns` | number | 15 | Smoke fix max iterations |
| `smoke_fix_max_retries` | number | 3 | Smoke fix max retries |
| `smoke_health_check_url` | string | "" | Health check URL |
| `smoke_health_check_timeout` | number | 30 | Health check timeout |
| `e2e_command` | string | "" | E2E test command |
| `e2e_timeout` | number | 120 | E2E timeout (seconds) |
| `e2e_mode` | enum | per_change | per_change / phase_end |

### Review and Verify

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `review_before_merge` | bool | false | LLM review gate |
| `max_verify_retries` | number | 2 | Verify retry limit |

### Token Control

Token control manages costs. The soft limit (`token_budget`) warns and slows down dispatch, but running agents can finish their work. The hard limit (`token_hard_limit`) stops the system and requests human approval — this is the ultimate safety net against unexpected token consumption.

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `token_budget` | number | 0 | Soft limit (0=off) |
| `token_hard_limit` | number | 20M | Hard limit |
| `checkpoint_auto_approve` | bool | false | Auto checkpoint approve |

### Planning

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `auto_replan` | bool | false | Auto-replan at phase end |
| `plan_method` | enum | api | api / agent |
| `plan_token_budget` | number | 500K | Agent plan budget |

### Watchdog

The watchdog is the "night guard": it intervenes when an agent is stuck and cannot proceed on its own. The timeout value should be tuned to the project's build time — if builds take 5 minutes, the 600s timeout is correct; if they take 30 seconds, consider lowering it to 180s.

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `watchdog_timeout` | number | 600 | Stall timeout (seconds) |
| `watchdog_loop_threshold` | number | 5 | Loop detection threshold |
| `max_redispatch` | number | 2 | Max redispatch attempts |

### Hooks

Hooks allow project-specific logic to be injected into the pipeline. The `pre_merge` hook is blocking: if it throws an error, the merge does not happen. Other hooks are non-blocking — if they error, the pipeline continues. The `post_merge_command` is the most commonly used hook: typically for database migration generation (Prisma, Drizzle) or build artifact refresh.

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `hook_pre_dispatch` | string | "" | Before dispatch |
| `hook_post_verify` | string | "" | After verify |
| `hook_pre_merge` | string | "" | Before merge (blocking) |
| `hook_post_merge` | string | "" | After merge |
| `hook_on_fail` | string | "" | On failure |
| `post_merge_command` | string | "" | Post-merge command |

### Event Log

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `events_log` | bool | true | Event log active |
| `events_max_size` | number | 1MB | Max log size |

## File Structure Reference

### Project-Level Files

```
.claude/
├── orchestration.yaml          ← configuration
└── orchestration.log           ← runtime log

wt/orchestration/
├── digest/
│   ├── requirements.json       ← REQ-XXX identifiers
│   ├── phases.json             ← phase structure
│   ├── digest-meta.json        ← hash, date
│   └── ambiguities.json        ← ambiguous points
└── specs/
    ├── v12.md                  ← active specs
    └── archive/
        └── v11.md              ← archived specs

orchestration-plan.json         ← current plan (gitignore)
orchestration-state.json        ← runtime state (gitignore)
orchestration-summary.md        ← summary (gitignore)
```

### Worktree-Level Files

```
.claude/worktrees/<change-name>/
├── .claude/
│   └── loop-state.json         ← Ralph loop state
├── openspec/changes/<name>/
│   ├── proposal.md             ← OpenSpec proposal
│   ├── design.md               ← design document
│   └── tasks.md                ← task list
└── ... (project files)
```

### Event Types

| Event | Description |
|-------|-------------|
| `STATE_CHANGE` | Change status transition |
| `DISPATCH` | Change dispatch |
| `MERGE_ATTEMPT` | Merge attempt |
| `MERGE_SUCCESS` | Successful merge |
| `MERGE_FAIL` | Failed merge |
| `VERIFY_PASS` | Verify gate pass |
| `VERIFY_FAIL` | Verify gate fail |
| `TEST_PASS` / `TEST_FAIL` | Test result |
| `SMOKE_PASS` / `SMOKE_FAIL` | Smoke test result |
| `WATCHDOG_ESCALATE` | Watchdog escalation |
| `CHECKPOINT` | Checkpoint activation |
| `REPLAN` | Replan start |
| `DIGEST_STARTED` / `DIGEST_FAILED` | Digest events |

Events are written to the `.claude/orchestration.log` JSONL file and can be queried with the `set-orchestrate events` command:

```bash
set-orchestrate events --type MERGE_SUCCESS --last 10 --json
```
