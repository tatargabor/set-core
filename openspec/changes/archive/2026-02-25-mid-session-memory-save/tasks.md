## 1. Turn counter infrastructure

- [x] 1.1 Add turn counter increment to `handle_user_prompt()` — after prompt extraction (line ~526), read `turn_count` from cache, increment, write back. Use `(( count++ )) || true` pattern for set -e safety.
- [x] 1.2 Add `last_checkpoint_turn` field initialization — set to 0 on first prompt if missing from cache. Add `CHECKPOINT_INTERVAL=15` constant near top of script.

## 2. Checkpoint save logic

- [x] 2.1 Add `_checkpoint_save()` helper function — reads `_metrics` entries from cache where index > last_checkpoint_turn count, extracts unique file paths (Read queries), Bash command count, and topic keywords (UserPromptSubmit queries). Formats as `[session checkpoint, turns N-M] Files: ... | Commands: N | Topics: ...` and calls `set-memory remember --type Context --tags "phase:checkpoint,source:hook"`.
- [x] 2.2 Add checkpoint trigger in `handle_user_prompt()` — after turn counter increment, check `turn_count - last_checkpoint_turn >= CHECKPOINT_INTERVAL`. If true, call `_checkpoint_save()` and update `last_checkpoint_turn`.

## 3. Write-save logic in PostToolUse

- [x] 3.1 Expand `handle_post_tool()` tool filter — change the early-exit condition from `Read/Bash only` to also accept `Write` and `Edit`. Route Write/Edit to new write-save logic before the existing Read/Bash recall path.
- [x] 3.2 Add `_write_save()` helper — extracts `file_path` from tool_input. For Write: saves `Modified <path> (new file)`. For Edit: saves `Modified <path>: <old_string[:100]> → changed`. Uses dedup key `WriteSave:<tool>:<file_path>` to avoid duplicates. Calls `set-memory remember --type Learning --tags "phase:write-save,source:hook"`.
- [x] 3.3 Add git commit detection in Bash handler — regex match `git commit` in Bash command text. Extract commit message (from `-m "..."` or `--message` flag). Save as `Committed: <message>`. Dedup key: `WriteSave:Bash:git-commit`.

## 4. Integration and testing

- [x] 4.1 Manual integration test — start a Claude session on a test project, make 15+ prompts and verify checkpoint save appears in `set-memory list`. Edit a file and verify write-save appears. Run `git commit` and verify commit-save appears.
- [x] 4.2 Verify existing recall behavior unchanged — confirm Read/Bash PostToolUse still injects recall context as before. Confirm UserPromptSubmit still performs proactive recall on every prompt.
