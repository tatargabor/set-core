# E2E Test Guide — Orchestration Monitoring

How to run and monitor wt-tools orchestration E2E tests.

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

Only fix **framework** (wt-tools) bugs. Let the orchestrator handle app-level issues.

**Framework bugs** — fix immediately, commit, deploy, restart:
- Dispatch/verify/merge state machine errors
- Path resolution failures in wt-tools modules
- Sentinel stuck detection false positives (e.g. during long MCP calls)
- Completion logic errors (e.g. all-failed treated as done)
- Infinite loops in replan/retry cycles

**App bugs** — leave to orchestrator:
- Build failures (Next.js, webpack, etc.)
- Test failures in the consumer project
- Missing dependencies, type errors
- Stale caches (`.next/`, `node_modules/`)

### When You Fix a wt-tools Bug

This is critical — fixes must reach the running processes:

1. **Fix and commit** in wt-tools repo
2. **Kill** sentinel + orchestrator + any Ralph/agent processes
3. **Deploy** — run `wt-project init` in the test project to sync `.claude/` files
4. **Sync worktrees** — for each active worktree, copy updated files:
   ```bash
   for wt in /tmp/minishop-runN-wt-*; do
     cp -r /tmp/minishop-runN/.claude/ "$wt/.claude/" 2>/dev/null
   done
   ```
5. **Restart** sentinel — it will start a new orchestrator automatically

If you skip step 4, worktree agents will run with old code.

**IMPORTANT: Rules must be re-deployed too.** Web security rules (`.claude/rules/web/`) and other
path-scoped rules are deployed by `wt-project init`. When fixing security-related bugs (IDOR,
missing auth middleware, etc.), always re-deploy so that retry agents get the updated rules. The
`wt-project init` + worktree sync (steps 3-4) handles this automatically — just don't skip them.

## State Reset

### Partial Reset (preferred — preserves merged work)

Only reset failed changes back to pending, keep merged ones:

```python
import json
with open('orchestration-state.json') as f:
    d = json.load(f)
for c in d['changes']:
    if c['status'] == 'failed':
        c['status'] = 'pending'
        c['worktree_path'] = ''
        c['ralph_pid'] = None
        c['verify_retry_count'] = 0
d['status'] = 'running'
with open('orchestration-state.json', 'w') as f:
    json.dump(d, f, indent=2)
```

### Full Reset (destructive — ask user first)

If many changes were already merged/done, **ask the user before resetting**.
Resetting destroys progress. Only do this if the state is truly unrecoverable.

```bash
# Clean worktrees
git worktree list | grep -v "bare\|master" | awk '{print $1}' | xargs -I{} git worktree remove {} --force
# Clean stale build caches
rm -rf .next node_modules/.cache
# Reset events
rm -f orchestration-state-events.jsonl
# Then reset state JSON (all changes → pending) and restart sentinel
```

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

Each E2E project gets its own findings directory **in the wt-tools repo**:

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
2. If a previous results block exists for the target project, extract the `<!-- wt-tools-commit: {hash} -->` and run `git log {hash}..HEAD --oneline` to get the commit delta
3. Read `tests/e2e/{project}/README.md` and latest `run-{N}.md` — list bugs that lack a "Verified" annotation or are marked "regressed"
4. List active changes in `openspec/changes/` (non-archived directories)
5. Return a summary in this format:

```
PREP SUMMARY ({project}, based on Run #{N}):
- wt-tools commits since last run: {count}
  {commit list, one per line}
- Open regressions: {bug numbers + short titles, or "none"}
- Active wt-tools changes: {change names + task progress}
- Watch for:
  - {specific patterns to monitor based on above}
```

Wait for subagent completion. Inject the summary into your context before proceeding.

### Phase 2: Launch

The sentinel launches the E2E run — not the user manually.

1. Run the scaffold script:
   ```bash
   ./tests/e2e/run.sh              # for minishop
   ./tests/e2e/run-complex.sh      # for craftbrew
   ```
2. Parse output for the created project directory path
3. `cd` to the project directory
4. Report the project directory to the user
5. Start orchestration:
   ```bash
   wt-sentinel --spec docs/v1-minishop.md    # minishop
   wt-sentinel --spec docs/v1.md             # craftbrew (check spec path)
   ```

### Phase 3: Monitor

Follow the existing guide sections:
- **Monitoring** — poll template, process checks
- **Framework Bug vs App Bug** — only fix framework bugs
- **When You Fix a wt-tools Bug** — fix → commit → deploy → sync → restart
- **State Reset** — partial preferred, full only with user approval

**Use prep context during monitoring:**
- When a failure occurs, check against the "Watch for" list from prep
- If a failure matches a known regression pattern, reference the bug number
- If a wt-tools commit addressed a specific bug, verify whether the fix holds

### Phase 4: Wrap-up

After orchestration completes (status "done", "stopped", or "time_limit"):

1. Run the report tool with guide update:
   ```bash
   wt-e2e-report --update-guide /path/to/wt-tools/tests/e2e/E2E-GUIDE.md
   ```
2. Create `tests/e2e/{project}/run-{N}.md` with findings from this run, update `tests/e2e/{project}/README.md` summary table
3. Commit changes to the wt-tools repo:
   ```bash
   cd /path/to/wt-tools
   git add tests/e2e/E2E-GUIDE.md tests/e2e/{project}/
   git commit -m "e2e: {project} run #{N} results"
   ```

**Even for failed/interrupted runs**: still run wrap-up to record partial results.

### Parallel Runs

Two E2E tests (minishop + craftbrew) can run simultaneously:
- Each has its own project dir (`/tmp/minishop-runN`, `/tmp/craftbrew-runN`)
- Each has its own findings file and results subsection in this guide
- Launch two separate sentinel sessions — they won't conflict
- Each sentinel's wrap-up updates only its own project block

## Last Run Results

<!-- Auto-updated by wt-e2e-report --update-guide. Do not edit between start/end markers. -->

<!-- e2e-results:minishop:start -->
### minishop — Run #19 (2026-03-17)
<!-- wt-tools-commit: 957d125d9 -->
- **wt-tools range**: `957d125d9` (review template f-string fix, decompose stderr logging)
- **Result**: 9/12 merged | ~4h | 4.1M tokens | 2 sentinel interventions (manual merge)
- **Open regressions**: Bug #50 (state reconstruction loses merged status), git_failed spam during verify/merge
- **Fixed this run**: Bug #49 `7551be1f5` (decompose stderr logging), Bug #51 `957d125d9` (review template f-string crash — major blocker)
- **Watch for run #20**: Bug #50 (state reconstruction) needs code fix. git_failed spam needs investigation. Merge step hangs requiring manual wt-merge — possibly related to git_failed. cart-management and order-views failed on review:critical + retry exhaustion.
<!-- e2e-results:minishop:end -->

<!-- e2e-results:craftbrew:start -->
<!-- e2e-results:craftbrew:end -->

## Architecture Quick Reference

The orchestration pipeline:
```
sentinel → orchestrator → digest → decompose → dispatch → agent (Ralph/wt-loop) → verify → merge → next phase
```

When looking for logic to fix, search the Python modules first (`lib/wt_orch/*.py`). If not found there, check the bash layer (`lib/orchestration/*.sh`). The migration is ongoing — some logic exists in both places but only one path is active for each function.
