## 1. Post-merge command directive (already partially implemented)

- [x] 1.1 Add `DEFAULT_POST_MERGE_COMMAND` constant and `post_merge_command` to `parse_directives()` case statement
- [x] 1.2 Add `post_merge_command` to jq JSON output in `parse_directives()`
- [x] 1.3 Add `post_merge_command` execution block in `merge_change()` — after dep install, before build verify
- [x] 1.4 Read `post_merge_command` from `directives` in `monitor_loop()` and include in log line

## 2. Directives persistence in state.json (already implemented)

- [x] 2.1 Add `update_state_field "directives"` after `init_state` in `cmd_start()` fresh start path
- [x] 2.2 Add `update_state_field "directives"` after `init_state` in resume path (status=stopped/time_limit)
- [x] 2.3 Add `update_state_field "directives"` after `init_state` in replan path
- [x] 2.4 Verify: write a test that starts orchestrator with `post_merge_command` set and confirms `.directives.post_merge_command` appears in state.json

## 3. Scope verification

- [x] 3.1 Add `verify_merge_scope()` function in `bin/set-orchestrate` — takes change_name, checks `git diff --name-only HEAD~1` for non-openspec files
- [x] 3.2 Call `verify_merge_scope()` in the post-merge pipeline after custom command, before build verify
- [x] 3.3 On failure (only openspec files in diff): log error + send critical notification, but do NOT block pipeline
- [x] 3.4 On success: log "Post-merge: scope verification passed for {change_name}"

## 4. Sentinel role boundary

- [x] 4.1 Rewrite guardrails section in `.claude/commands/wt/sentinel.md` — role boundary: observe/diagnose/restart/stop/report
- [x] 4.2 Add explicit forbidden actions list (no file modification, no config changes, no build commands)
- [x] 4.3 Deploy updated sentinel.md to all registered projects via `set-project init`

## 5. Documentation

- [x] 5.1 Add `post_merge_command` to the orchestrator help text (usage section in `set-orchestrate`)
- [x] 5.2 Add `post_merge_command` example in the Config section of `set-orchestrate` help
