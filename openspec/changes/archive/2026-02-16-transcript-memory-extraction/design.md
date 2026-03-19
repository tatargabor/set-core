## Context

The memory architecture has 3 layers that all depend on agent compliance:
1. CLAUDE.md ambient instructions ("save when you discover something")
2. SKILL.md inline hooks ("run `set-memory remember` at step 7")
3. Stop hook text reminder ("MEMORY REMINDER: run your recall/remember steps")

In practice, agents focused on the main task skip all three. The `wt-hook-memory-save` Stop hook currently only extracts `**Choice**:` lines from `design.md` after git commits — it misses session-level insights entirely.

The Stop hook receives `transcript_path` on stdin (a JSONL file with the full session conversation), but the current script discards it with `cat > /dev/null`.

Transcript JSONL structure:
- `type: "assistant"` entries contain `message.content[]` with `tool_use` blocks
- Skill invocations: `{"type": "tool_use", "name": "Skill", "input": {"skill": "opsx:apply", "args": "change-name"}}`
- Tool results, user messages, and agent responses are all present

The `claude` CLI supports `-p` (print mode) with `--model haiku` for cheap one-shot LLM calls (~$0.01).

## Goals / Non-Goals

**Goals:**
- Automatically extract session insights after opsx/openspec skill execution — no agent compliance required
- Save errors, learnings, user corrections, and discovered patterns to `set-memory`
- Only trigger when opsx/openspec skills were active (not on every stop)
- Keep existing commit-based design choice extraction as parallel path

**Non-Goals:**
- Replacing the existing 3 layers (they stay as-is for when they DO work)
- Extracting from non-opsx sessions (too noisy, too expensive)
- Real-time mid-session extraction (this is post-session only)

## Decisions

### 1. Transcript detection: grep for Skill tool_use with opsx/openspec

**Choice**: Scan the JSONL file with grep for `"skill":"opsx:` and `"skill":"openspec-` patterns to detect whether skills were used.

**Alternatives considered:**
- Check `.set-core/agents/*.skill` marker files → stale state, unreliable after agent exit
- Always run extraction → too expensive, noisy on non-skill sessions

### 2. LLM extraction: `claude -p --model haiku`

**Choice**: Use `claude` CLI in print mode with haiku model for cheap, reliable insight extraction. Unset `CLAUDECODE` env var to avoid nesting check.

**Alternatives considered:**
- Direct Anthropic API via curl → needs raw API key management, more code
- Structured text parsing without LLM → fragile, can't understand intent/context
- Full opus/sonnet call → too expensive for a hook that runs frequently

### 3. Transcript window: last ~100 JSONL lines

**Choice**: Extract the last ~100 lines of the transcript for the LLM to analyze. This covers the most recent skill execution without overwhelming the context.

**Alternatives considered:**
- Full transcript → too large for sessions with multiple skills, expensive
- Only tool_result entries → misses user corrections and agent reasoning
- Skill-bounded extraction (from Skill invocation to end) → complex parsing, multiple skills may overlap

### 4. Output format: one `set-memory remember` call per insight

**Choice**: The LLM outputs structured lines (type|tags|content) that the hook script parses and feeds to `set-memory remember` one by one.

Format:
```
Learning|error,<change>|Description of the error and fix
Decision|preference,<change>|User said to always do X
```

### 5. Execution model: synchronous within the hook

**Choice**: Run the LLM call synchronously in the Stop hook. The 30s timeout should be sufficient for haiku (typically 3-8s). If it times out, the hook fails silently (exit 0) — no data loss, just no extraction for that session.

**Alternatives considered:**
- Background async process → orphan process management, harder to debug
- Separate cron/daemon → over-engineered for the use case

### 6. Deduplication: skip if agent already saved memories

**Choice**: Check if the transcript contains evidence of successful `set-memory remember` calls by the agent. If the agent already saved memories (grep for "Memory saved:" or "Agent insights saved:" in the transcript), reduce extraction scope to only find things the agent missed.

## Risks / Trade-offs

- **[Cost]** ~$0.01 per opsx session via haiku → Acceptable; only fires on skill sessions. Mitigation: skip if agent already saved (most common case if compliance improves).
- **[Timeout]** 30s hook timeout may be tight → Mitigation: haiku is fast (3-8s typical). If timeout, fails silently.
- **[Quality]** Haiku may extract low-quality or noisy insights → Mitigation: strict extraction prompt with examples; max 3 insights per session; require concrete/actionable content.
- **[Nesting]** `claude` CLI blocks nesting via CLAUDECODE env → Mitigation: `CLAUDECODE= claude -p` to unset.
- **[Privacy]** Session transcript sent to haiku → Same trust boundary (Anthropic API), transcript already lives in Claude's systems.
