## Why

The memory system's only hard save point is the Stop hook (session-end transcript extraction). If a session crashes, times out, or the user closes the terminal before the Stop hook runs, all learned knowledge is lost. Active projects (eg-sales: 11 memories from 20+ commits, itline-web: 13 memories from 30+ commits) show suspiciously low memory counts, suggesting many sessions end without proper extraction. Mid-session checkpoints and tool-triggered saves would prevent this data loss.

## What Changes

- Add a **turn counter** to `handle_user_prompt()` in `wt-hook-memory` that triggers lightweight memory extraction every N turns (default: 15). The extraction summarizes accumulated context from the session dedup cache's metrics array, using the same haiku-based extraction as the Stop hook but on a rolling window.
- Add a **write-save trigger** to `handle_post_tool()` that automatically saves a "what changed and why" Learning memory after Write/Edit tool use and after Bash commands containing `git commit`. This uses tool input parameters directly (no LLM call needed) — file path, old/new content summary, and commit message.
- Extend the **session dedup cache** (`/tmp/wt-memory-session-*.json`) with `turn_count`, `last_checkpoint_turn`, and `checkpoint_entries` fields for checkpoint state tracking.

## Capabilities

### New Capabilities
- `turn-checkpoint-save`: Periodic mid-session memory extraction triggered by turn count threshold in UserPromptSubmit hook
- `posttool-write-save`: Automatic memory save after file modifications (Write/Edit) and git commits in PostToolUse hook

### Modified Capabilities
- `unified-memory-hook`: Add checkpoint dispatch in UserPromptSubmit handler and write-save dispatch in PostToolUse handler
- `posttool-memory-surfacing`: Expand scope from Read/Bash-only recall to also include Write/Edit/Bash save triggers

## Impact

- `bin/wt-hook-memory`: Main changes — `handle_user_prompt()` gets turn counter + checkpoint trigger, `handle_post_tool()` gets Write/Edit/Bash(commit) save logic
- Session dedup cache: Extended with checkpoint tracking fields
- Memory volume: Expected ~3-5 additional memories per long session (checkpoints) + ~1 per file modification (write-saves)
- Hook timeout: UserPromptSubmit checkpoint extraction needs haiku call (~5-8s) — may need timeout increase from 15s to 20s for checkpoint turns only
- No new dependencies — uses existing `wt-memory remember` CLI and haiku extraction patterns from Stop hook
