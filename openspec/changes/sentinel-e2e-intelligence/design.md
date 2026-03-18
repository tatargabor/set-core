# Design: sentinel-e2e-intelligence

## Overview

Three layers of change: (A-C) intelligence additions to the existing sentinel, (D) a new E2E sentinel mode with framework fix authority, (E) extracting state reset into a safe standalone CLI tool.

## A: Tier 1 Expansion — Expected Patterns

Add these to the sentinel skill's Tier 1 (defer) table with explicit explanations so the sentinel doesn't misinterpret them:

```
| Pattern | Why it's OK | Duration |
|---------|-------------|----------|
| Post-merge build fail (prisma/codegen) | post_merge_command handles this | 1-2 min |
| Watchdog "no progress" on fresh dispatch | New agents need 1-2 min startup | 2 min |
| Stale build cache (.next/, dist/) | Build retry clears this | 1 build cycle |
| Long MCP fetch (design, memory) | Heartbeat events confirm liveness | 4-5 min |
| waiting:api loop status | wt-loop exponential backoff handles 429/503 | auto |
```

**Where**: `.claude/commands/wt/sentinel.md` — expand the table after line 27.

## B: Token Stuck Detection

Add a per-change token+commit check to the poll summary parsing. The poll script already emits `tokens=`. Enhancement:

1. **In the poll script**: add per-change token tracking
   ```bash
   # Per-change stuck detection
   STUCK=$(jq '[.changes[] | select(.status == "running") |
     select(.tokens_used > 500000) |
     select(.last_commit_at == null or
       (.last_commit_at | fromdateiso8601) < (now - 1800))] |
     length' "$STATE_FILE" 2>/dev/null || echo "0")
   if [ "$STUCK" -gt 0 ]; then
     echo "WARNING:token_stuck|count=$STUCK"
   fi
   ```

2. **In EVENT:running handler**: if WARNING:token_stuck present, escalate to user once (not every poll)

3. **In completion report**: add per-change token breakdown with stuck flags

**Where**: `.claude/commands/wt/sentinel.md` — poll script (Step 2) and completion report (Step 5).

## C: Dependency Deadlock Detection

Add to poll script:

```bash
# Dependency deadlock: pending changes whose deps are all failed
DEADLOCKED=$(jq '[.changes[] | select(.status == "pending") |
  select(.depends_on != null and (.depends_on | length) > 0) |
  select(all(.depends_on[]; . as $dep |
    [$.changes[] | select(.name == $dep) | .status][0] == "failed"))] |
  length' "$STATE_FILE" 2>/dev/null || echo "0")
if [ "$DEADLOCKED" -gt 0 ]; then
  echo "WARNING:deadlocked|count=$DEADLOCKED"
fi
```

**Handler**: On first detection, report to user with the specific change names and their failed dependencies. Don't auto-fix — the user decides whether to clear deps or mark as failed.

**Where**: Same locations as B.

## D: E2E Sentinel Mode (Tier 3)

### Activation

Not a flag — it's a separate section in the sentinel skill doc that the E2E lifecycle (Phase 3) references. The user pastes E2E-specific instructions when starting an E2E run.

### Tier 3 Scope Boundary

```
┌────────────────────────────────────────────┐
│           Tier 3: Fix + Deploy              │
│                                             │
│  ALLOWED:                                   │
│  ├── Edit files in wt-tools repo            │
│  │   (bin/, lib/, .claude/, docs/)          │
│  ├── git commit in wt-tools repo            │
│  ├── wt-project init (deploy .claude/)      │
│  ├── cp -r .claude/ to worktrees            │
│  ├── Kill sentinel/orchestrator/agents      │
│  ├── Restart sentinel                       │
│  │                                          │
│  FORBIDDEN:                                 │
│  ├── Consumer project source code           │
│  │   (src/, app/, components/, etc.)        │
│  ├── Branch merge/resolve                   │
│  ├── orchestration-state.json edits         │
│  ├── Quality gate changes                   │
│  │   (smoke_command, test_command, etc.)     │
│  └── Architectural/design decisions         │
└────────────────────────────────────────────┘
```

### Workflow

1. Sentinel detects framework bug (e.g., dispatch error, path resolution, state machine bug)
2. Sentinel identifies the fix location (always in wt-tools, never consumer project)
3. Fix → commit → `wt-project init` → sync worktrees → kill → restart
4. Log the fix as a finding (`wt-sentinel-finding add`)
5. Resume polling

### Where

- `tests/e2e/E2E-GUIDE.md` — add Tier 3 reference in "When You Fix a wt-tools Bug" section
- `.claude/commands/wt/sentinel.md` — add E2E Mode section (after guardrails, clearly separated) with Tier 3 scope and workflow

## E: wt-orchestrate reset CLI

### Subcommand

```bash
wt-orchestrate reset --partial              # safe: failed→pending
wt-orchestrate reset --full --yes-i-know    # destructive: everything→pending + clean worktrees
wt-orchestrate reset                        # defaults to --partial
```

### Partial Reset (safe default)

```python
for change in state['changes']:
    if change['status'] == 'failed':
        change['status'] = 'pending'
        change['worktree_path'] = ''
        change['ralph_pid'] = None
        change['verify_retry_count'] = 0
state['status'] = 'running'
```

### Full Reset (destructive, requires flag)

```bash
# 1. Backup state
cp orchestration-state.json orchestration-state.backup.json

# 2. Clean worktrees
git worktree list | grep -v "bare\|master\|main" | awk '{print $1}' |
  xargs -I{} git worktree remove {} --force

# 3. Reset all changes to pending
# 4. Clear events log
# 5. Print what was reset
```

### Safety

- `--full` without `--yes-i-know` → prints what would be destroyed and exits
- Always creates backup before destructive operations
- Prints summary: "Reset 3 failed→pending, 4 merged preserved" (partial) or "Reset ALL 7 changes, removed 3 worktrees" (full)

### Where

- `bin/wt-orchestrate` — add `reset` subcommand
- Remove state reset snippets from sentinel scope (`.claude/commands/wt/sentinel.md`)
- Update `tests/e2e/E2E-GUIDE.md` "State Reset" section to reference `wt-orchestrate reset`

## File Impact Summary

| File | Changes |
|------|---------|
| `.claude/commands/wt/sentinel.md` | A: Tier 1 expansion, B: token stuck, C: deadlock, D: E2E mode section, E: remove reset guidance |
| `bin/wt-orchestrate` | E: add `reset` subcommand |
| `tests/e2e/E2E-GUIDE.md` | D: Tier 3 reference, E: update reset section to use CLI |
| `docs/sentinel.md` | Sync changes from skill (Tier 1 expansion, E2E mode mention) |
