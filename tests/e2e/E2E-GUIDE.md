# E2E Test Guide — Orchestration Monitoring

How to run and monitor set-core orchestration E2E tests.

## Quick Start

Start a new Claude Code session and paste:

```
Futtasd az E2E minishop tesztet.
Olvasd el a tests/e2e/E2E-GUIDE.md-t és kövesd a "Sentinel E2E Lifecycle" szekciót elejétől végéig.
```

For craftbrew:
```
Futtasd az E2E craftbrew tesztet.
Olvasd el a tests/e2e/E2E-GUIDE.md-t és kövesd a "Sentinel E2E Lifecycle" szekciót elejétől végéig.
```

## Monitoring

### Poll Template

Set up a cron job that checks these 5 things concisely:

1. **Processes alive?** — sentinel + orchestrator PIDs
2. **State** — overall status, how many running/merged/failed/pending
3. **Log tail** — last 15 lines of `.claude/orchestration.log` for errors/warnings
4. **Worktrees** — `git worktree list` to see active agent worktrees
5. **Events** — tail + count of `orchestration-state-events.jsonl`

### Framework Bug vs App Bug

Only fix **framework** (set-core) bugs. Let the orchestrator handle app-level issues.

**Framework bugs** — fix immediately, commit, deploy, restart:
- Dispatch/verify/merge state machine errors
- Path resolution failures in set-core modules
- Sentinel stuck detection false positives (e.g. during long MCP calls)
- Completion logic errors (e.g. all-failed treated as done)
- Infinite loops in replan/retry cycles

**App bugs** — leave to orchestrator:
- Build failures (Next.js, webpack, etc.)
- Test failures in the consumer project
- Missing dependencies, type errors
- Stale caches (`.next/`, `node_modules/`)

### When You Fix a set-core Bug

This is the **Tier 3** workflow from the sentinel skill (`.claude/commands/wt/sentinel.md` — "E2E Mode" section). Fixes must reach the running processes:

1. **Fix and commit** in set-core repo
2. **Kill** sentinel + orchestrator + any Ralph/agent processes
3. **Deploy** — run `set-project init` in the test project to sync `.claude/` files
4. **Sync worktrees** — for each active worktree, copy updated files:
   ```bash
   for wt in $(git worktree list --porcelain | grep '^worktree ' | awk '{print $2}' | tail -n +2); do
     cp -r .claude/ "$wt/.claude/" 2>/dev/null
   done
   ```
5. **Restart** sentinel — it will start a new orchestrator automatically
6. **Log** — `set-sentinel-finding add --severity bug --summary "..." ` with commit hash

If you skip step 4, worktree agents will run with old code.

**Scope boundary (Tier 3):** Only set-core framework code may be fixed (bin/, lib/, .claude/, docs/). Consumer project source code (src/, app/, components/) MUST NOT be modified. No branch merging, no orchestration-state.json edits, no quality gate changes.

**IMPORTANT: Rules must be re-deployed too.** Web security rules (`.claude/rules/web/`) and other
path-scoped rules are deployed by `set-project init`. When fixing security-related bugs (IDOR,
missing auth middleware, etc.), always re-deploy so that retry agents get the updated rules. The
`set-project init` + worktree sync (steps 3-4) handles this automatically — just don't skip them.

## State Reset

Use the dedicated CLI tool:

```bash
# Partial reset (safe default) — only failed→pending, merged preserved
set-orchestrate reset --partial

# Full reset (destructive) — shows dry-run first
set-orchestrate reset --full

# Full reset (confirmed) — backs up state, removes worktrees, clears events
set-orchestrate reset --full --yes-i-know
```

**Always prefer partial reset.** Full reset destroys progress — only use if state is truly unrecoverable, and always ask the user first.

## Figma Design Integration

The orchestrator automatically:
1. Detects Figma MCP in `.claude/settings.json`
2. Reads `design_file` URL from `wt/orchestration/config.yaml`
3. Fetches design snapshot via 4 sequential MCP calls (~4-5 min)
4. Injects design tokens into planning and dispatch contexts

**Verify it works:**
- `design-snapshot.md` appears in project root (should be ~10KB)
- Log shows "Design snapshot saved" and "Design bridge active"
- If missing: check MCP registration, `design_file` config, Figma auth

**Sentinel stuck detection:** Design fetch takes 4-5 minutes. The framework emits heartbeat events during this time. If sentinel kills the orchestrator during fetch, that's a framework bug — fix the heartbeat emission.

## Token Budget

Watch `tokens_used` per change in the state file. Expected ranges:
- **S complexity**: 300K–600K tokens
- **M complexity**: 600K–1M tokens
- **L complexity**: 1M+ (avoid — split into smaller changes)

If a change exceeds ~500K without progress (no new commits, cycling same error), it's stuck. The orchestrator has built-in retry limits (`max_verify_retries: 2`).

Token tracking may show zero while the agent is still running — only trust the count after the Ralph loop has completed.

## Expected Patterns (Not Bugs)

These look like failures but are normal and auto-resolve:

- **Post-merge Prisma client errors** — first 2–3 merges may fail build on main because schema changes don't trigger `prisma generate`. Add `npx prisma generate` to `post_merge_command` in config.yaml. The auto-fix mechanism resolves this without intervention.
- **Watchdog "no progress" warnings during artifact creation** — newly dispatched changes take 1-2 min before the first loop-state.json appears. The watchdog has a grace period for this.
- **Stale `.next/` cache** — `rm -rf .next` before build fixes this. Not a framework issue.

## Known Framework Limitations

- **Dependency cascade deadlock**: If a dependency fails, dependent changes may stay `pending` forever instead of being marked `failed`. Workaround: manually set dependent changes to `failed` or `pending` with cleared deps.
- **Digest re-generation fragility**: In later replan cycles (N>2), digest JSON parsing can fail. The spec digest should ideally be frozen once validated.

## Performance Baseline

From 6 E2E runs (4 MiniShop, 2 CraftBrew):

| Metric | Good Run | Typical |
|---|---|---|
| Wall clock (6 changes) | 1h 45m | 2h |
| Changes merged | 6/6 | 6/7 |
| Sentinel interventions | 0 | 1 |
| Total tokens | 2.7M | 4M |
| Verify retries | 5 | 10+ |

Compare each run against these baselines. Track: wall clock, merged/failed ratio, total tokens, interventions needed.

## Run Findings — Storage & Workflow

### Where findings go

Each E2E project gets its own findings directory **in the set-core repo**:

```
tests/e2e/{project}/          # version-controlled, permanent record
  README.md                   # summary table + bug index across runs
  run-{N}.md                  # per-run findings (one file per run)
```

Examples:
- `tests/e2e/minishop/` — MiniShop orchestration runs (run-13, run-14, run-15, ...)

### When to write

Write findings **continuously during the run**, not after:

1. **Bug found** → append to findings file immediately (even before fix)
2. **Bug fixed** → update the entry with commit hash and deploy status
3. **Phase completes** → add status table and timing data
4. **Run ends** → write Final Run Report section with metrics

### Per-bug template

```markdown
### N. [short description]
- **Type**: framework / app
- **Severity**: blocking / noise
- **Root cause**: ...
- **Fix**: [commit hash] — deployed to running test? yes/no
- **Recurrence**: new / seen in run N-1
```

### Final Run Report template

```markdown
## Final Run Report

### Status: COMPLETED / INTERRUPTED / PARTIAL (X/Y merged)

| Change | REQs | Status | Tokens | Time | Notes |
|--------|------|--------|--------|------|-------|
| ... | ... | merged/FAILED | ... | ... | ... |

### Key Metrics
- **Wall clock**: Xh Ym
- **Changes merged**: X/Y (Z%)
- **Sentinel interventions**: N
- **Total tokens**: XM
- **Bugs found & fixed**: N
- **Verify retries**: N

### Conclusions
1. ...
```

### Cross-run tracking

Number bugs sequentially across runs within the same project file (e.g. Run #1 bugs 1-7, Run #2 bugs 8-14). This makes it easy to reference bugs across runs and track recurrence.

## Sentinel E2E Lifecycle

The sentinel (Claude agent mode via `/wt:sentinel`) owns the full E2E lifecycle. The user tells it which project to run; the sentinel handles everything else.

### Phase 1: Prep (subagent — protects sentinel context)

Spawn a subagent to collect context. The sentinel does NOT read findings/git log itself — the subagent returns a compact summary (~20 lines).

**Subagent instructions:**
1. Read `tests/e2e/E2E-GUIDE.md` — especially "Last Run Results" and "Performance Baseline"
2. If a previous results block exists for the target project, extract the `<!-- set-core-commit: {hash} -->` and run `git log {hash}..HEAD --oneline` to get the commit delta
3. Read `tests/e2e/{project}/README.md` and latest `run-{N}.md` — list bugs that lack a "Verified" annotation or are marked "regressed"
4. List active changes in `openspec/changes/` (non-archived directories)
5. Return a summary in this format:

```
PREP SUMMARY ({project}, based on Run #{N}):
- set-core commits since last run: {count}
  {commit list, one per line}
- Open regressions: {bug numbers + short titles, or "none"}
- Active set-core changes: {change names + task progress}
- Watch for:
  - {specific patterns to monitor based on above}
```

Wait for subagent completion. Inject the summary into your context before proceeding.

### Phase 2: Launch

The sentinel launches the E2E run — not the user manually.

1. Run the scaffold script:
   ```bash
   ./tests/e2e/run.sh              # for minishop (default: ~/.local/share/set-core/e2e-runs/)
   ./tests/e2e/run-complex.sh      # for craftbrew (default: ~/.local/share/set-core/e2e-runs/)

   # To override base dir:
   ./tests/e2e/run.sh --project-dir ~/other-dir
   ./tests/e2e/run-complex.sh --project-dir ~/other-dir
   ```
2. Parse output for the created project directory path
3. `cd` to the project directory
4. Report the project directory to the user
5. Start orchestration:
   ```bash
   set-sentinel --spec docs/v1-minishop.md    # minishop
   set-sentinel --spec docs/v1.md             # craftbrew (check spec path)
   ```

### Phase 3: Monitor

Follow the existing guide sections:
- **Monitoring** — poll template, process checks
- **Framework Bug vs App Bug** — only fix framework bugs
- **When You Fix a set-core Bug** — fix → commit → deploy → sync → restart
- **State Reset** — partial preferred, full only with user approval

**Use prep context during monitoring:**
- When a failure occurs, check against the "Watch for" list from prep
- If a failure matches a known regression pattern, reference the bug number
- If a set-core commit addressed a specific bug, verify whether the fix holds

### Phase 4: Wrap-up

After orchestration completes (status "done", "stopped", or "time_limit"):

1. Run the report tool with guide update:
   ```bash
   set-e2e-report --update-guide /path/to/set-core/tests/e2e/E2E-GUIDE.md
   ```
2. Create `tests/e2e/{project}/run-{N}.md` with findings from this run, update `tests/e2e/{project}/README.md` summary table
3. Commit changes to the set-core repo:
   ```bash
   cd /path/to/set-core
   git add tests/e2e/E2E-GUIDE.md tests/e2e/{project}/
   git commit -m "e2e: {project} run #{N} results"
   ```

**Even for failed/interrupted runs**: still run wrap-up to record partial results.

### Parallel Runs

Two E2E tests (minishop + craftbrew) can run simultaneously:
- Each has its own project dir (`~/.local/share/set-core/e2e-runs/minishop-runN`, `.../craftbrew-runN`)
- Each has its own findings file and results subsection in this guide
- Launch two separate sentinel sessions — they won't conflict
- Each sentinel's wrap-up updates only its own project block

## Last Run Results

<!-- Auto-updated by set-e2e-report --update-guide. Do not edit between start/end markers. -->

<!-- e2e-results:minishop:start -->
### minishop — Run #19 (2026-03-17)
<!-- set-core-commit: 5c741058c -->
- **set-core range**: `5c741058c` (review diff prioritization, merge heartbeats, review template fix, decompose stderr)
- **Result**: 11/12 merged + 1 skipped | ~8h (incl. retry run) | ~5M tokens | 4 framework bugs found
- **Open regressions**: Bug #50 (state reconstruction loses merged status)
- **Fixed this run**: Bug #49 `7551be1f5` (decompose stderr), Bug #51 `957d125d9` (review template f-string), Bug #52 `5c741058c` (merge heartbeats), Bug #53 `ab018fa88` (review diff prioritization — root cause of false review failures)
- **Watch for run #20**: Bug #50 needs fix (Python monitor doesn't emit STATE_CHANGE events). Sentinel bash syntax error on line 536 needs investigation.
<!-- e2e-results:minishop:end -->

<!-- e2e-results:craftbrew:start -->
### craftbrew — Run #4 (2026-03-19)
<!-- set-core-commit: 65d6258be -->
- **set-core range**: `65d6258be` (scaffold spec-only branch, decompose max-turns, sentinel stuck fix, gitattributes wt/**)
- **Result**: 5/15 merged (2 failed, 8 dep-blocked) | ~3h wall clock | ~998K tokens | 4 framework bugs found
- **Autonomous merges**: 4/5 (80%) — massive improvement over Run #3's 1/15 (7%)
- **Bug #14 (verify agent death)**: NOT REPRODUCED — verify pipeline reliability fix confirmed working
- **Bug #16 (sentinel stuck)**: Fixed mid-run — 600s timeout + live children check (`dcc12d587`)
- **New bugs**: Bug #20 (scaffold stale branch), Bug #21 (decompose max-turns), Bug #22 (sentinel timeout), Bug #23 (wt/** gitattributes)
- **Blocker**: Dependency cascade deadlock — `auth-system` failure blocked 6/8 remaining changes
- **Watch for run #5**: Dependency cascade handling (auto-skip or replan around failed deps). Consider removing GitHub repo dependency (local spec files).
<!-- e2e-results:craftbrew:end -->

## Architecture Quick Reference

The orchestration pipeline:
```
sentinel → orchestrator → digest → decompose → dispatch → agent (Ralph/set-loop) → verify → merge → next phase
```

When looking for logic to fix, search the Python modules first (`lib/set_orch/*.py`). If not found there, check the bash layer (`lib/orchestration/*.sh`). The migration is ongoing — some logic exists in both places but only one path is active for each function.
