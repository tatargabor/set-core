## 1. Raw Transcript Filter

- [x] 1.1 Implement `_stop_raw_filter()` function in `bin/wt-hook-memory` — parse full JSONL transcript, apply word-count/pattern filters (user <15 chars, assistant <50 chars, system-reminder, repeated file reads)
- [x] 1.2 Add change-name extraction from opsx/openspec skill invocations (reuse existing logic from `_stop_extract_from_transcript`)
- [x] 1.3 Add context prefix formatting: `[session:<change>, turn N/total]` on each saved turn
- [x] 1.4 Save filtered turns via `set-memory remember` with tags `raw,phase:auto-extract,source:hook,change:<name>` — user turns as Context type, assistant turns as Learning type

## 2. Stop Handler Rewrite

- [x] 2.1 Replace `_stop_extract_from_transcript()` Haiku LLM flow with call to `_stop_raw_filter()`
- [x] 2.2 Remove staging file logic (`_stop_commit_staged`, `.staged-extract-*` files, `.ts` timestamp files, debounce check)
- [x] 2.3 Add one-time migration: commit any existing `.set-core/.staged-extract-*` files from previous Haiku sessions before switching to raw filter
- [x] 2.4 Keep background execution pattern (disowned process) for the raw filter

## 3. PreToolUse Removal

- [x] 3.1 Modify `handle_pre_tool()` in `bin/wt-hook-memory` to exit 0 immediately with no output (no memory recall)
- [x] 3.2 Remove PreToolUse matchers for Read, Edit, Write, Bash, Task, Grep from `.claude/settings.json` (keep activity-track.sh Skill matcher)

## 4. PostToolUse Simplification

- [x] 4.1 Modify `handle_post_tool()` to only process Read and Bash tools — exit 0 immediately for Edit, Write, Task, Grep
- [x] 4.2 Remove "Modified FILE" FileAccess memory saves (Edit/Write context saves)
- [x] 4.3 Remove Bash error pattern saves from PostToolUse (keep PostToolUseFailure for error recall)
- [x] 4.4 Remove proactive recall from PostToolUse — keep only direct recall with dedup check
- [x] 4.5 Update PostToolUse matchers in `.claude/settings.json` to only match Read and Bash

## 5. Verification

- [x] 5.1 Test raw filter on a real transcript JSONL — verify filter rules, context prefix, and memory saves work correctly
- [x] 5.2 Verify PreToolUse no longer fires memory recall (check `/tmp/wt-hook-memory.log`)
- [x] 5.3 Verify PostToolUse only fires for Read and Bash (check log for Edit/Write/Task/Grep absence)
- [x] 5.4 Verify existing staged files are committed during one-time migration
