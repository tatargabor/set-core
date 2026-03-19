## Context

The current memory hook system uses 2 Claude Code hook events: `UserPromptSubmit` (recall) and `Stop` (save). Recall only fires on OpenSpec "change boundaries" — when a new change name is detected in the prompt. This means explore mode, non-OpenSpec usage, and intermediate steps (like DB queries triggered mid-task) get zero automatic memory injection.

Additionally, 8 OpenSpec skills and 8 opsx commands contain inline `<!-- set-memory hooks -->` blocks that instruct the agent to manually call `set-memory recall` and `set-memory remember`. This is a workaround for the hooks not covering enough lifecycle events. The CLAUDE.md "Proactive Memory" section has similar manual instructions.

Comparing with the shodh-memory reference implementation (v0.1.80), they use a single `memory-hook.ts` that handles 6 hook lifecycle events with `additionalContext` injection. Their CLAUDE.md simply says "hooks handle everything, use `remember` only for emphasis." The inline skill instructions are unnecessary when hooks work properly.

### Claude Code Hook API (from official docs)

Key capabilities we'll leverage:
- **`additionalContext`**: Available on SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure — injects text into Claude's context
- **`PostToolUseFailure`**: Separate event that fires specifically when tools fail (not PostToolUse) — ideal for error recovery
- **PreToolUse matcher `"Bash"`**: Matches tool name, then script parses `tool_input.command` for patterns
- **Plain text stdout on UserPromptSubmit/SessionStart**: Automatically added as context (exit 0)
- **async hooks**: Available but NOT useful for PreToolUse (can't inject context before tool runs)

## Goals / Non-Goals

**Goals:**
- Memory recall fires on every user prompt (L2), not just change boundaries
- Hot-topic commands get proactive memory injection before execution (L3)
- Tool failures trigger automatic error-pattern recall (L4)
- Session starts with relevant project context pre-loaded (L1)
- All layers work without OpenSpec — OpenSpec enriches but isn't required
- Existing haiku transcript extraction (L5) enhanced with cheat-sheet curation
- Minimal latency: 0ms for non-hot-topic Bash, ~150ms for hot-topic Bash, ~200ms for prompt recall
- **Remove ALL inline memory instructions from skills, commands, and CLAUDE.md** — hooks handle everything
- Agent uses `set-memory remember` only for emphasis, not routine recall/save

**Non-Goals:**
- MCP server for memory (out of scope — keep CLI-based for now)
- Read tool content parsing (detecting DB references in file contents — too complex, too slow)
- Real-time memory streaming during tool execution
- Cross-session cheat sheet sharing (each machine has its own)
- Changing skill logic or OpenSpec workflow (only removing memory hook blocks)

## Decisions

### Decision 1: Five-layer hook architecture

**Choice**: Implement 5 layers using 4 new/modified hook events (SessionStart, UserPromptSubmit, PreToolUse/PostToolUseFailure, Stop).

**Alternatives considered**:
- Single omniscient hook on UserPromptSubmit: simpler but can't help mid-task
- MCP server approach (like shodh-memory): more powerful but larger scope, new dependency
- Skill-embedded instructions only: already proven unreliable on fresh installs

**Rationale**: Each layer catches different situations. L2 catches intent ("what does the user want?"), L3 catches action ("what is the agent doing?"), L4 catches outcome ("what went wrong?"). No single layer covers all three.

### Decision 2: Use `PostToolUseFailure` (not `PostToolUse`) for L4

**Choice**: Hook into `PostToolUseFailure` event specifically for error recovery.

**Alternatives considered**:
- PostToolUse with exit code check: PostToolUse only fires on success per docs
- PostToolUse on all Bash: would fire on every successful command too (noisy)

**Rationale**: Claude Code has a dedicated `PostToolUseFailure` event that provides `error` and `is_interrupt` fields. This is the exact trigger we need — fires only on failures, gives us the error text for recall query.

### Decision 3: Synchronous PreToolUse for hot topics (not async)

**Choice**: L3 runs synchronously before Bash execution, blocking for ~150ms on hot-topic matches.

**Alternatives considered**:
- Async PreToolUse: can't inject `additionalContext` before tool runs (per docs: "Async hooks cannot block tool calls or return decisions")
- PostToolUse with preemptive context: too late — tool already ran

**Rationale**: The whole point of L3 is injecting context BEFORE the command runs. 150ms latency is negligible for DB/deploy commands that take seconds. Non-matching Bash calls exit immediately (pattern check is ~1ms).

### Decision 4: Project-discoverable hot-topic patterns with mid-session learning

**Choice**: Generic base pattern list + project-specific discovery at SessionStart (L1) + mid-session auto-promotion from errors (L4). Two feedback speeds: fast (within session) and slow (across sessions).

**Discovery sources** (scanned by L1 at session start):
1. `bin/*` → extract command prefixes (e.g., `wt-*`, `openspec`)
2. `package.json` scripts → npm/bun run targets
3. `Makefile` / `pyproject.toml` → project-specific commands
4. Memory tags with high frequency → frequently-discussed topics
5. Error memories → tools/commands that failed before
6. Memories tagged `hot-topic` → user-promoted topics from past sessions

**Mid-session auto-promotion** (L4 → hot-topics.json):
When L4 fires (PostToolUseFailure on Bash), it extracts the command prefix and appends it to `.claude/hot-topics.json`. Next time L3 runs, it reads the updated file and matches the new pattern.

Skip list for trivial commands (never promote): `ls, cat, head, tail, echo, cd, pwd, mkdir, cp, mv, touch, chmod, chown, wc, sort, grep, find, which, test, true, false, exit`

**Two feedback speeds:**
```
FAST (within session): L4 error → append to hot-topics.json → L3 catches next run
SLOW (across sessions): L5 saves error memory → L1 discovers next session
```

**Generic base patterns** (always active, project-independent):
```
REMOTE:      ssh\s|scp\s
DESTRUCTIVE: rm\s+-rf|drop\s|truncate\s|DELETE\s+FROM
ELEVATED:    sudo\s
CONTAINERS:  docker\s|kubectl\s|podman\s
```

**Cache file**: `.claude/hot-topics.json` — written by L1, updated by L4, read by L3. Structure:
```json
{
  "patterns": ["wt-\\w+", "openspec\\s", "cargo"],
  "generated_at": "2026-02-17T21:00:00Z",
  "promoted": ["cargo"]
}
```
The `promoted` array tracks mid-session additions (from L4) separately from L1 discovery for debugging. L1 overwrites the entire file at session start (promoted entries only persist if L5 saved them as error memories).

**Alternatives considered**:
- Hardcoded static list (psql, mysql, curl, etc.): doesn't adapt to project; useless for set-core which uses wt-*, openspec, git worktree
- Fully dynamic only: doesn't work on fresh install with zero memories
- User-only manual promotion: users won't do it; the goal is zero-config automation
- Frequency-based promotion (count Bash calls): requires per-call I/O overhead; bad trade-off
- Per-pattern recall hints: more targeted but added complexity not worth it — L3 can use the matched command itself as recall query

**Rationale**: Every project has different tools. Discovery at session start covers the known project structure. L4 auto-promotion covers the unknown — commands the agent encounters and fails at. Together they make L3 adaptive from the first error, without any user configuration.

### Decision 5: Topic extraction from prompt (L2) instead of change-boundary detection

**Choice**: Extract keywords from user prompt text for recall query. If OpenSpec change detected, also include change name.

**Algorithm**:
1. Extract prompt text from hook input JSON
2. If prompt contains `opsx:` or `openspec-` skill invocation → extract change name, use as primary query
3. Otherwise → use first 200 chars of prompt as recall query (set-memory handles semantic matching)
4. Always recall, no debounce/boundary check (set-memory proactive API handles relevance filtering)

**Alternatives considered**:
- Keep change-boundary detection + add topic fallback: complex, still misses explore
- LLM-based keyword extraction: too slow for a hook (adds 1-2s)

**Rationale**: The current change-boundary detection is the root cause of the problem. Removing it and always recalling is simpler and more reliable. `set-memory proactive` already handles relevance scoring — low-relevance results are filtered.

### Decision 6: Cheat sheet as tagged memories (not a separate file)

**Choice**: The "operational cheat sheet" (L1) is just memories tagged `cheat-sheet` that get loaded at SessionStart.

**Alternatives considered**:
- Separate `.claude/cheat-sheet.md` file: another thing to maintain, sync issues
- Part of CLAUDE.md: can't be project-specific per machine, gets bloated

**Rationale**: Using tagged memories means: (1) cheat sheet entries are searchable by L2/L3/L4, (2) they sync via `set-memory sync`, (3) they leverage existing importance/decay mechanics, (4) L5 can promote entries to cheat-sheet by adding the tag.

### Decision 7: L5 cheat-sheet promotion (non-interactive)

**Choice**: At session end (Stop hook), the haiku extraction step evaluates whether error→fix patterns should be cheat-sheet entries. Convention entries get automatic cheat-sheet promotion.

**Flow**:
1. Existing haiku extraction runs (unchanged)
2. If extracted memories include error→fix patterns, additionally tag with `cheat-sheet`
3. L1 picks these up on next session start

**Alternatives considered**:
- Interactive user prompt ("should this be in your cheat sheet?"): blocks session end, annoying
- Agent-based hook to decide: too slow, too expensive

**Rationale**: Stop hooks should be fast and non-blocking. The haiku model can decide cheat-sheet worthiness during extraction at no extra cost.

### Decision 8: Separate scripts per layer

**Choice**: Each layer is a separate script file: `wt-hook-memory-warmstart` (L1), `wt-hook-memory-recall` (L2, rewritten), `wt-hook-memory-pretool` (L3), `wt-hook-memory-posttool` (L4), `wt-hook-memory-save` (L5, enhanced).

**Alternatives considered**:
- Single script with event dispatch (like shodh-memory's memory-hook.ts): harder to debug, test, and maintain
- Inline hooks in settings.json: can't do complex logic

**Rationale**: Separate scripts are testable independently, have clear responsibility boundaries, and match our existing pattern (wt-hook-memory-recall, wt-hook-memory-save).

### Decision 9: Remove ALL inline memory instructions from skills and commands

**Choice**: Delete all `<!-- set-memory hooks -->` blocks from 8 skills and 8 commands. Hooks handle recall (L2 on every prompt) and save (L5 on every stop) — skills don't need to duplicate this.

**What gets removed**:
- `hooks start/end` blocks (recall at skill start)
- `hooks-midflow start/end` blocks (save user insights during work)
- `hooks-remember start/end` blocks (save after implementation)
- `hooks-reflection start/end` blocks (agent self-reflection at session end)
- `hooks-save start/end` blocks (save after verification)

**What stays in skills**: The skill logic itself. No memory-related code.

**Alternatives considered**:
- Keep skill hooks alongside automatic hooks: causes double-recall, double-save, dedup problems
- Keep only recall hooks in skills, remove save: half-measure, still complex
- Make skills "opt out" of automatic hooks: adds complexity to hook scripts

**Rationale**: Following shodh's principle — "This is not a tool you query, it is part of how you think." If hooks work correctly, the agent doesn't need instructions to manually recall or save. The hooks fire on EVERY prompt (L2) and EVERY stop (L5), which covers all skill invocations automatically.

### Decision 10: CLAUDE.md "Persistent Memory" rewrite (shodh-style)

**Choice**: Replace the current "Proactive Memory" section (~36 lines of manual recall/save instructions) with a ~15-line "Persistent Memory" section that:
1. Explains hooks handle recall and save automatically
2. Agent uses `set-memory remember` only for HIGH IMPORTANCE emphasis (critical decisions, user-stated preferences)
3. Agent uses `set-memory forget` to suppress/correct wrong memories
4. No manual `set-memory recall` instructions — context appears automatically via hooks
5. No "When to save" / "When NOT to save" rules — L5 handles extraction

**Template** (adapted from shodh):
```markdown
## Persistent Memory

This project uses persistent memory (shodh-memory) across sessions. Hooks handle memory automatically — you don't need to manage it.

**Automatic (invisible to you):**
- Session start → relevant memories loaded
- Every prompt → topic-based recall injected
- Tool errors → past fixes surfaced
- Session end → insights extracted and saved

**Emphasis (use sparingly):**
- `set-memory remember --type <Decision|Learning|Context> --tags <tags>` — mark something as HIGH IMPORTANCE
- `set-memory forget <id>` — suppress or correct a wrong memory
- Most things are remembered automatically. Only use these for emphasis.
```

**Alternatives considered**:
- Keep detailed save/recall rules: contradicts hook-driven approach, agents get confused about who's responsible
- Remove memory section entirely: agent needs to know memory exists and how to emphasize

**Rationale**: The current CLAUDE.md creates a conflict — it tells the agent to manually recall/save, but hooks also recall/save, leading to duplication. Shodh solved this by making the agent aware of memory but not responsible for operating it.

## Risks / Trade-offs

**[Risk] PreToolUse latency on hot-topic commands** → Mitigation: Pattern check is ~1ms (regex), only recall (~150ms) on match. Non-hot-topic Bash calls have zero overhead. Monitor with `--debug` flag.

**[Risk] Too many memories injected (context bloat)** → Mitigation: Each layer limits results (L1: 5, L2: 3, L3: 2, L4: 3). Use `additionalContext` (discrete) not plain stdout (visible). Total worst case: ~15 short memory lines.

**[Risk] set-memory server not running** → Mitigation: Every script starts with `command -v set-memory &>/dev/null || exit 0; set-memory health &>/dev/null || exit 0`. Silent exit, zero impact.

**[Risk] PostToolUseFailure fires on non-error failures (user interrupt)** → Mitigation: Check `is_interrupt` field, skip if true.

**[Risk] Duplicate recall across L2 and L3** → Mitigation: L2 recalls broadly (prompt-level), L3 recalls narrowly (command-specific). Different query = different results. Even with overlap, Claude deduplicates naturally.

**[Risk] wt-deploy-hooks backwards compatibility** → Mitigation: Upgrade path already exists in deploy-hooks. Add new hook types incrementally. Existing projects get new hooks on next `wt-deploy-hooks` run.

**[Risk] Removing skill hooks breaks memory for projects that haven't upgraded hooks** → Mitigation: The deploy script runs on `wt-add` (project registration). Any project managed by set-core gets hooks deployed. Projects not managed by set-core were never using the skills anyway.

**[Risk] Hot-topic discovery finds too many patterns** → Mitigation: L1 caps discovered patterns at 20. Generic base patterns kept minimal (4 categories). Cache file is human-readable for debugging.

## Open Questions

1. **L3 timeout**: Should PreToolUse have a 5s or 10s timeout? Recall usually takes <500ms but network/server issues could cause hangs. Current: propose 5s.
2. **L4 error dedup**: If the same error repeats 3 times in a session, should L4 recall on every failure or debounce? Current: propose recall every time (memories may have been saved mid-session by L5).
3. **Hot-topic discovery refresh**: Should L3 re-discover if cache is older than 24h? Or only on SessionStart? Current: propose SessionStart only.
