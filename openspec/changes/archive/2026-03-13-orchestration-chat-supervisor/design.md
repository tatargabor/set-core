## Context

The orchestration chat tab (`lib/set_orch/chat.py`) uses `claude -p --resume {session_id}` to maintain multi-turn conversations. Currently it passes no context about the agent's role — it's a generic Claude session in the project directory.

The `claude` CLI supports `--append-system-prompt` which adds text to the default system prompt (preserving CLAUDE.md loading). This is the injection point.

The orchestration state lives in `wt/orchestration/orchestration-state.json` (typed dataclasses in `lib/set_orch/state.py`). Config lives in `.claude/orchestration.yaml`.

## Goals / Non-Goals

**Goals:**
- Agent knows it's an orchestration supervisor on every turn
- Agent sees fresh orchestration state on every message (not stale from session start)
- Agent knows which bash commands to use for querying and controlling orchestration
- Agent responds in Hungarian by default
- Context is compact enough to not bloat token usage (~500-1000 tokens)

**Non-Goals:**
- Auto-polling / proactive monitoring (Level 3 — future work)
- Frontend changes
- Replacing the sentinel skill (sentinel runs in its own terminal, this is for mobile/web)
- Modifying orchestration logic itself

## Decisions

### D1: `--append-system-prompt` over `--system-prompt`

**Choice:** Use `--append-system-prompt`
**Rationale:** `--system-prompt` replaces the entire system prompt including CLAUDE.md loading. `--append-system-prompt` adds to it, preserving all project context, rules, MCP tools, and skills. The agent needs both project knowledge AND supervisor role.

### D2: Build context on every message, not just session start

**Choice:** Call `build_chat_context(project_path)` before every `_run_claude()` invocation
**Rationale:** With `--resume`, the session persists across invocations. But `--append-system-prompt` is passed per invocation, so we can refresh it. This means the agent always sees the latest state — a change may have completed between two user messages.

### D3: Compact state summary, not raw JSON dump

**Choice:** Format state as a human-readable summary table, not raw JSON
**Rationale:** Raw `orchestration-state.json` can be 10-50KB. A formatted summary (change name, status, tokens, last activity) fits in ~200-500 tokens. The agent can always `cat` the full file if it needs detail.

### D4: Separate module `chat_context.py`

**Choice:** New file `lib/set_orch/chat_context.py` with a single `build_chat_context(project_path) -> str` function
**Rationale:** Keeps chat.py focused on WS/subprocess lifecycle. Context building involves file I/O and formatting — separate concern. Easy to test and extend.

### D5: Hungarian language default in system prompt

**Choice:** System prompt instructs "Válaszolj magyarul."
**Rationale:** Primary user is Hungarian. Can be made configurable later via orchestration.yaml if needed.

## Risks / Trade-offs

- **[Token overhead]** ~500-1000 tokens per message for system prompt → Mitigated by compact formatting and summarized state. Negligible compared to CLAUDE.md + rules (~4-8K tokens).
- **[Stale state between read and invocation]** State file read is not atomic with Claude invocation → Acceptable; state changes over seconds, not milliseconds. Agent can always re-read.
- **[--append-system-prompt not on --resume]** If `--append-system-prompt` is ignored on `--resume` invocations → Test confirmed it works. If it breaks in future claude CLI versions, fall back to prefixing user message.
- **[File not found]** Project may not have orchestration-state.json (no orchestration running) → Context builder handles gracefully: "Nincs aktív orchestration."
