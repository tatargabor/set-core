[< Back to Guides](README.md)

# Orchestration

set-core's orchestration engine transforms a specification document into merged, verified code — autonomously. It decomposes your spec into parallel changes, dispatches each to an isolated git worktree with its own Claude Code agent, and shepherds every change through quality gates before merging to main.

---

## Pre-Run Checklist

Before starting orchestration, verify these items. Spec quality directly determines output quality — a vague spec produces a generic app.

- [ ] **Spec review** — Does the spec have concrete details (page layouts, component names, data models)? Not just "add a cart page" but "cart page with item table, quantity controls, coupon input, and order summary sidebar."
- [ ] **Design sync** — If you have a Figma design, run `set-design-sync --input docs/design.make --spec-dir docs/` to inject design tokens into specs. Without this, agents use framework defaults. See [Design Integration](design-integration.md).
- [ ] **Config review** — Check `set/orchestration/config.yaml` for correct `test_command`, `e2e_command`, `merge_policy`, and `env_vars`.
- [ ] **Project health** — Run `/set:audit` to catch missing dependencies, broken configs, or stale state from previous runs.

---

## The Pipeline

Orchestration proceeds through seven stages. Each stage is automatic; the only required human input is the initial spec.

### 1. Digest

The engine reads your specification document and extracts structured requirements. Each requirement gets a unique ID, category, and priority. The digest serves as the ground truth for spec coverage tracking later in the pipeline.

```bash
set-orchestrate --spec docs/v3-release.md plan
```

For large specs, focus on a subset with `--phase`:

```bash
set-orchestrate --spec docs/v3-release.md --phase 1 plan
set-orchestrate --spec docs/v3-release.md --phase "Security" plan
```

### 2. Decompose

An LLM analyzes the digest and breaks it into sized, independent changes with a dependency DAG. Each change gets:

- A name, scope description, and complexity rating (S / M / L / XL)
- A list of requirements it addresses
- Dependencies on other changes (respected during dispatch)

The plan is saved to `orchestration-plan.json`. Review it before execution:

```bash
set-orchestrate plan --show
```

With `plan_approval: true` in config, the engine pauses here until you run `set-orchestrate approve`.

### 3. Dispatch

For each change whose dependencies are satisfied (up to `max_parallel` concurrently), the engine:

1. Creates a git worktree branched from main
2. Generates an `input.md` proposal with scope, requirements, and review learnings
3. Starts a **Ralph Loop** — an autonomous Claude Code agent that implements the change through iterative code-test-fix cycles

Each worktree is fully isolated. Agents cannot interfere with each other or with main.

### 4. Monitor

A 15-second poll cycle checks every active change:

- **Progress tracking** — reads each agent's `loop-state.json` for iteration count, status, and token usage
- **Stall detection** — the watchdog monitors file hashes; if nothing changes across consecutive polls, it escalates through warn, resume, kill, and fail levels
- **Crash recovery** — if an agent's PID is dead but the change is not done, the watchdog attempts a restart
- **Token budget enforcement** — warns at 80%, pauses at 100%, fails at 120% of the per-change budget

When a change reports "done," the engine moves it to verification.

### 5. Verify

Every completed change passes through a sequence of quality gates before it can merge. Gates run inside the worktree against the change's branch.

| Gate | What it checks | Pass criteria |
|------|---------------|---------------|
| **test** | Unit/integration tests (`vitest run`, `pytest`, etc.) | Exit code 0 |
| **build** | Type checking and compilation (`tsc --noEmit`, `next build`) | Exit code 0 |
| **e2e** | End-to-end tests (Playwright, Cypress) | Exit code 0 |
| **review** | LLM code review for correctness, security, style | No CRITICAL findings |
| **smoke** | Post-merge smoke test on main | Exit code 0 |
| **spec_coverage** | Requirements addressed vs. digest | All assigned requirements covered |

If a gate fails, the agent receives the error output and retries (up to `max_verify_retries`, default 2). Gate results are recorded as `VERIFY_GATE` events.

Gate verdicts are parsed by the **unified LLM verdict classifier** (`lib/set_orch/llm_verdict.py`): a small Sonnet second-pass reads the primary output as unstructured text and returns a JSON object describing pass/fail, critical count, and findings. This replaced fragile regex parsing and closes the "silent pass" bug where a retry review that said "3 NOT_FIXED [CRITICAL]" in an unrecognised format slipped through.

![Changes tab showing gate badges](../images/auto/web/tab-changes.png)

### 6. Merge

Changes that pass verification enter a sequential merge queue (one merge at a time). The merge pipeline:

1. **Fast-forward merge** to main (ff-only when possible)
2. **Conflict resolution** — if ff-only fails, an LLM-based resolver attempts automatic conflict resolution
3. **Post-merge verification** — dependency install, build check, and smoke test on main
4. **Worktree cleanup** — the merged worktree is removed and the change is archived

If conflict resolution fails, the change enters `merge-blocked` status. Other changes continue; you can resolve manually and retry with `set-orchestrate approve <name>`.

Merge policies control when merges happen:

| Policy | Behavior |
|--------|----------|
| `eager` | Merge each change as it completes |
| `checkpoint` | Batch merges every N changes, wait for approval |
| `manual` | Queue all merges, flush on `set-orchestrate approve --merge` |

### 7. Replan

After all planned changes merge, the engine checks for remaining spec coverage gaps. With `auto_replan: true`, it generates a new plan targeting uncovered requirements and starts the next phase automatically. This continues until the spec is fully covered or no novel changes can be generated.

---

## Quality Gates

Gates are driven by the project's **profile** (the `ProjectType` plugin). The profile detects which tools are available (vitest, playwright, tsc) and configures gate commands accordingly. You can also set commands explicitly in `orchestration.yaml`.

| Gate | Default detection | Override config |
|------|------------------|-----------------|
| test | `vitest run`, `pytest`, `go test` | `test_command` |
| build | `tsc --noEmit`, `next build` | `build_command` |
| e2e | `playwright test`, `cypress run` | `e2e_command` |
| review | LLM review (sonnet, auto-escalates on failure) | `review_model` |
| smoke | Runs on main after merge | `smoke_command`, `smoke_timeout` |
| spec_coverage | Compares change output to digest requirements | `require_full_coverage` |

Gate failures produce structured output in `review-findings.jsonl`, which feeds into the review learnings system — preventing the same mistakes across future changes and runs.

### Review Learnings

The review learnings pipeline closes a loop across changes and runs: each review finding is classified, semantically deduped, and persisted to a per-project checklist. The checklist is then injected into **both** sides of future runs:

- **Agent side** — `input.md` carries a scope-filtered slice of the checklist (filtered by diff content category: auth / api / database / frontend), so agents see only relevant patterns. Between ralph iterations `input.md` is refreshed when the checklist file's mtime advances, so in-flight changes pick up learnings from changes that merged while they were running.
- **Review side** — the review gate prompt now receives the same checklist and can BLOCK changes that violate past patterns. Previously the "review will BLOCK if violated" header was an empty promise because the checklist never reached the reviewer.

Dedup is LLM-based (Sonnet merge pass) so semantically identical patterns consolidate instead of bloating the 200-entry eviction cap. Severity calibration has an explicit rubric (CRITICAL is reserved for crash/leak/data-loss) and the classifier records any downgrades it applied.

### State Archives and Journals

Every overwrite of a tracked `state.json` field (gate results, outputs, timings, retry context, status, current_step) appends a row to `<orchestration_dir>/journals/<change-name>.jsonl`. A general-purpose `archive_and_write()` helper also snapshots tracked files before overwriting, storing them under `<orchestration_dir>/archives/<relative-path>/<ts>.<ext>`. Post-merge, a worktree harvest copies `.set/reflection.md`, `.set/loop-state.json`, `.set/activity.json`, and `.claude/review-findings.md` into `<orchestration_dir>/archives/worktrees/<change-name>/` so the artefacts survive worktree cleanup.

In the dashboard, each gate tab now shows per-run sub-tabs driven by the journal API — you can inspect earlier Build/Test/E2E/Review attempts, not just the last one. Legacy changes without journals fall back to the single-run view.

---

## Dashboard

The web dashboard (port 7400) provides real-time visibility into orchestration runs. Select a project from the manager, then explore tabs for changes, phases, tokens, digest, log, sessions, and more.

![Changes tab with gate badges and status](../images/auto/web/tab-changes.png)

![Phases tab showing phase grouping](../images/auto/web/tab-phases.png)

For a full tour of all dashboard tabs and features, see the [Dashboard guide](dashboard.md).

---

## Configuration

Create `.claude/orchestration.yaml` in your project root:

```yaml
# Parallelism
max_parallel: 3

# Merge behavior
merge_policy: eager          # eager | checkpoint | manual
checkpoint_every: 3          # for checkpoint policy

# Quality gates
test_command: vitest run
build_command: tsc --noEmit
smoke_command: pnpm test:smoke
smoke_timeout: 120
review_model: ""             # auto-selects; set explicitly to override

# Token budgets
max_tokens_per_change: 0     # 0 = complexity defaults (S=500K, M=2M, L=5M, XL=10M)

# Automation
auto_replan: true            # auto-advance to next phase
plan_approval: false         # require manual approval after plan generation
time_limit: 5h               # max wall-clock time

# Post-merge
post_merge_command: ""       # e.g., pnpm db:generate for Prisma

# Watchdog
watchdog_timeout: ""         # seconds before stall detection
watchdog_loop_threshold: ""  # identical hashes before loop detection
```

### Precedence

Settings resolve in this order (highest wins):

1. CLI flags (`--max-parallel`, `--time-limit`)
2. Config file (`.claude/orchestration.yaml`)
3. In-document directives (`## Orchestrator Directives` section in your spec)
4. Built-in defaults

> **Config edits require supervisor restart.** `set/orchestration/config.yaml`
> is read once at startup and cached in `directives.json`. Later edits to
> `config.yaml` DO NOT take effect on a running orchestrator — the engine
> detects the drift on next restart and logs a `CONFIG_DRIFT` WARNING +
> event, but it keeps using the directives parsed at startup. To apply
> changes: stop the supervisor, restart it (it will reparse `config.yaml`).

### Hooks

Lifecycle hooks run scripts at key transitions:

| Hook | When | Blocking? |
|------|------|-----------|
| `hook_pre_dispatch` | Before dispatching a change | Yes |
| `hook_post_verify` | After verification passes | Yes |
| `hook_pre_merge` | Before merge | Yes |
| `hook_post_merge` | After successful merge | No |
| `hook_on_fail` | When a change fails | No |

Hook scripts receive `(change_name, status, worktree_path)` as arguments.

---

## Troubleshooting

### Agent stuck (no progress)

The watchdog detects stalled agents through file hash monitoring. Escalation levels:

1. **Warn** — logs warning, emits `WATCHDOG_WARN` event
2. **Resume** — attempts to restart the stalled agent
3. **Kill** — terminates the process and retries
4. **Fail** — marks the change as failed, salvages partial work as `partial-diff.patch`

If the entire orchestrator stops producing events, the sentinel (if running) detects the silence and restarts it.

### Merge failed

**Conflict:** The LLM resolver could not produce clean output. The change enters `merge-blocked` status. Resolve conflicts manually in the worktree, then run `set-orchestrate approve <change-name>`.

**Post-merge build failure:** The smoke test or build check failed on main after merge. An LLM agent (sonnet, 20 turns) attempts an automatic fix. If auto-fix fails, a critical notification is emitted and the pipeline continues.

### Gate failure

When a gate fails, the agent receives the full error output and retries up to `max_verify_retries` times. Common causes:

- **test gate** — flaky tests, missing test dependencies. Check the worktree's test output.
- **build gate** — type errors from incomplete implementation. The agent usually self-corrects on retry.
- **review gate** — CRITICAL finding (security issue, missing error handling). The agent addresses the finding and re-submits.
- **e2e gate** — browser tests failing. Often caused by missing test fixtures or incorrect selectors.

Use `set-orchestrate events --type VERIFY_GATE` to see all gate results across the run.

### Distinguishing infra failure from verdict failure

The `spec_verify` gate classifies each LLM invocation into three categories:

- **verdict** — LLM output contains `VERIFY_RESULT: PASS` or `FAIL`. Sentinel is authoritative; exit code is secondary. Normal flow — pass/fail behavior as documented above.
- **infra** — LLM hit `--max-turns` without producing a verdict, OR the subprocess timed out. Infrastructure failure, not a code fault. The gate retries once with doubled turn budget (40→80). If the retry also lands in infra, the gate returns `skipped` with `infra_fail=True` on the emitted `VERIFY_GATE` event. Retry slot is **not** consumed; implementation agent is **not** re-dispatched.
- **ambiguous** — No sentinel, no detectable infra cause. Falls through to the classifier fallback path (second Sonnet pass to extract a structured verdict).

To filter infra anomalies from real findings in run logs:

```bash
set-orchestrate events --type VERIFY_GATE | jq 'select(.data.infra_fail == true)'
```

The `infra_fails` array on the event lists which gates abstained and why (`terminal_reason: "max_turns"` or `"timeout"`). These are usually a sign of a pathological prompt (the LLM getting stuck re-running the same command) or a consumer project whose verify surface is too large for the default budget. Repeated infra failures on the same change warrant operator attention rather than more retries.

### Token budget exceeded

Per-change budgets are based on complexity:

| Complexity | Budget |
|------------|--------|
| S | 500K |
| M | 2M |
| L | 5M |
| XL | 10M |

Override with `max_tokens_per_change` in config. The watchdog warns at 80%, pauses at 100%, and fails at 120%.

### State corruption

If `orchestration-state.json` becomes inconsistent (e.g., after a crash), the engine reconstructs state from `orchestration-events.jsonl` automatically on next startup. You can also query the event log directly:

```bash
set-orchestrate events --last 20
set-orchestrate events --type ERROR
```

---

*See also: [Sentinel](sentinel.md) | [Worktrees](worktrees.md) | [Configuration](../reference/configuration.md) | [Architecture](../reference/architecture.md)*

*Next: [Sentinel](sentinel.md) | [Worktrees](worktrees.md) | [Quick Start](quick-start.md)*

<!-- specs: orchestration-engine, dispatch-core, verify-gate, merger, gate-profiles, orchestration-watchdog -->
