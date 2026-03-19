## Context

`wt-deploy-hooks` deploys Claude Code hook settings to projects. After `raw-conversation-ingest`, the canonical config is:
- PreToolUse: `Skill` only (activity-track.sh)
- PostToolUse: `Read`, `Bash` only (wt-hook-memory)

But many projects still have the old expanded config (6 PreToolUse + 6 PostToolUse memory matchers). The deploy script's idempotency check sees "unified hooks present" and skips, never downgrading.

## Goals / Non-Goals

**Goals:**
- `wt-deploy-hooks` can downgrade stale configs to match the canonical hook set
- Only removes `wt-hook-memory` entries — never touches non-wt hooks (activity-track.sh, user-added)
- Works transparently via existing `install.sh` → `set-project init` → `wt-deploy-hooks` flow

**Non-Goals:**
- Changing the canonical hook config itself (that was `raw-conversation-ingest`)
- Adding a `--force` flag (surgical comparison is better)
- Migrating non-registered projects (user must run `set-project init` manually)

## Decisions

### Decision 1: Compare actual entries against canonical set, not count-based heuristics

**Rationale:** Counting matchers (e.g. "PreToolUse >= 7") is fragile — a user could add their own hooks. Instead, iterate the actual entries and compare each against the canonical set. If an entry has `wt-hook-memory PreToolUse` or `wt-hook-memory PostToolUse` command AND its matcher is NOT in the canonical set, remove it.

**Canonical matcher sets:**
- PreToolUse wt-hook-memory: **none** (Skill matcher uses activity-track.sh, not wt-hook-memory)
- PostToolUse wt-hook-memory: `Read`, `Bash`
- All other events: unchanged (SessionStart, UserPromptSubmit, PostToolUseFailure, SubagentStop, Stop)

### Decision 2: Use jq filter to prune stale entries in-place

**Rationale:** The current script already uses jq for detection and merging. A jq filter can walk PreToolUse/PostToolUse arrays and remove entries where the command matches `wt-hook-memory` but the matcher is not in the allowed set. This is a single `jq` invocation, no temp files beyond the standard pattern.

### Decision 3: Replace "skip if unified" with "skip if canonical"

Current logic:
```
has_unified = SessionStart + PostToolUse.exists + SubagentStop → SKIP
```

New logic:
```
is_canonical = no stale wt-hook-memory entries in PreToolUse/PostToolUse → SKIP
```

The check becomes: "are there any wt-hook-memory entries in PreToolUse or PostToolUse that shouldn't be there?" If yes → prune. If no → skip.

## Risks / Trade-offs

**[Risk] User manually added wt-hook-memory entries for a reason** → Mitigation: Unlikely. The command is internal. But the prune only targets PreToolUse and PostToolUse, and only entries whose command is exactly `wt-hook-memory PreToolUse` or `wt-hook-memory PostToolUse`. Custom commands wouldn't match.

**[Risk] Backup created on every downgrade** → Mitigation: Already standard behavior. `.bak` is overwritten each run, not accumulated.
