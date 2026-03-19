## Context

The memory system has a single hard save point: the Stop hook at session end. All mid-session hooks (UserPromptSubmit, PostToolUse) only perform recall. If a session crashes, times out, or the user closes the terminal, all knowledge from that session is lost. Diagnosis shows active projects have suspiciously low memory counts (eg-sales: 11, itline-web: 13) despite heavy commit activity, confirming the Stop hook frequently doesn't run.

The existing infrastructure already supports what we need:
- Session dedup cache (`/tmp/set-memory-session-*.json`) persists across hook events within a session and already stores frustration_history and _metrics
- `handle_user_prompt()` (line 521) fires on every user prompt — natural place for turn counting
- `handle_post_tool()` (line 683) fires after tool use but currently only handles Read/Bash for recall
- `set-memory remember` CLI is the standard save interface
- The Stop hook's `_stop_raw_filter()` provides a template for transcript-based extraction

## Goals / Non-Goals

**Goals:**
- Add turn-based checkpoint saves in UserPromptSubmit (every ~15 turns)
- Add automatic write-save after Write/Edit tools and git commits
- Use the existing session dedup cache for state tracking
- Keep checkpoint extraction lightweight (sub-10s, fits within hook timeout)

**Non-Goals:**
- Replacing the Stop hook — it remains the comprehensive session-end extraction
- LLM-based extraction for write-saves — tool parameters provide enough context
- Compression event hooks — Claude Code has no such event
- Changing the dedup cache format fundamentally — only extending with new keys

## Decisions

### Decision: Turn counter in dedup cache, not metrics counting
**Choice**: Add an explicit `turn_count` integer to the session dedup cache, incremented on every UserPromptSubmit call.
**Why not count _metrics entries**: The _metrics array also contains PostToolUse, PostToolUseFailure, and SubagentStop entries — counting only UserPromptSubmit events would require filtering. A dedicated counter is simpler, O(1), and less fragile.

### Decision: Checkpoint extraction via accumulated metrics summary, not transcript re-reading
**Choice**: On checkpoint turns, summarize the accumulated `_metrics` entries since last checkpoint (which tools were used, which files were read/written, what prompts were given) and save as a single Context memory. No LLM call needed.
**Why not re-read transcript**: The transcript file is append-only and could be huge. Reading it mid-session adds I/O overhead and complexity. The _metrics array already captures a structured summary of every hook event. Format: `[session checkpoint, turn N] Files read: X, Commands run: Y, Topics: Z`

### Decision: Write-save extracts from tool_input JSON, no LLM
**Choice**: For Write/Edit PostToolUse events, extract `file_path` from tool_input and save a brief Learning memory: `"Modified <file_path>: <first 200 chars of change context>"`. For Bash events containing `git commit`, extract the commit message.
**Why no LLM**: tool_input already contains the file path and content. Calling haiku adds 3-5s latency to every file write, which would noticeably slow the agent. Direct extraction keeps it under 100ms.

### Decision: Checkpoint interval of 15 turns, configurable
**Choice**: Default to 15 turns between checkpoints. Store `last_checkpoint_turn` in cache. Checkpoint fires when `turn_count - last_checkpoint_turn >= 15`.
**Why 15**: A typical productive session has 30-60 turns. At 15-turn intervals, we get 2-4 checkpoints per session. Too frequent (5) creates noise; too infrequent (30) defeats the purpose.

### Decision: Write-save scope — Write, Edit, and Bash(git commit) only
**Choice**: Save after Write and Edit tool use. For Bash, only save when the command contains `git commit` (detected by regex). Skip all other Bash commands, Glob, Grep, Read, etc.
**Why not all Bash**: Most Bash calls are reads (ls, git status, cat). Saving after each would create massive noise. Only commits represent persistent state changes worth recording.

## Risks / Trade-offs

- **[Risk: Checkpoint timeout]** UserPromptSubmit has 15s timeout. Checkpoint save adds ~200ms (cache read + set-memory remember). Safe within budget. → If future checkpoints become heavier, add timeout guard.
- **[Risk: Write-save noise]** Frequent file edits (e.g., iterating on a single file) could create many similar memories. → Dedup by file path: only save first modification per file per session (use existing dedup mechanism with key `"WriteSave:$TOOL:$FILE_PATH"`).
- **[Risk: Cache file growth]** Adding checkpoint entries increases cache file size. → Keep checkpoint_entries as a simple array of strings, pruned on each checkpoint (only keep entries since last checkpoint, not all history).
- **[Risk: PostToolUse timeout]** PostToolUse hooks have no explicit timeout issue — write-save is a simple set-memory remember call (<100ms). Low risk.
