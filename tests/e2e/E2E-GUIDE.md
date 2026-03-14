# E2E Test Guide — Orchestration Monitoring

How to run and monitor wt-tools orchestration E2E tests.

## Quick Start

```bash
# 1. Create test project (auto-increments run number)
./tests/e2e/run.sh

# 2. Start sentinel (from the created directory)
cd /tmp/minishop-runN
wt-sentinel --spec docs/v1-minishop.md

# 3. Monitor with cron (every 3 minutes)
# Use the poll template below
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

Watch token usage in the state file (`tokens_used` per change). If a single change exceeds ~500K tokens without progress (no new commits, cycling on the same error), it's likely stuck. The orchestrator has built-in retry limits (`max_verify_retries: 2`) but may need intervention if the scope is fundamentally too large.

## Known Issues

Document bugs found during each run in a findings section. Include:
- Root cause (framework vs app)
- Fix commit hash
- Whether it was deployed to the running test
- Severity: did it block progress or just cause noise?

## Architecture Quick Reference

The orchestration pipeline:
```
sentinel → orchestrator → digest → decompose → dispatch → agent (Ralph/wt-loop) → verify → merge → next phase
```

When looking for logic to fix, search the Python modules first (`lib/wt_orch/*.py`). If not found there, check the bash layer (`lib/orchestration/*.sh`). The migration is ongoing — some logic exists in both places but only one path is active for each function.
