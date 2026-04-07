# Tasks: Resume Context Restoration

## 1. Add resume preamble helper

- [x] 1.1 In `lib/set_orch/dispatcher.py`, add `_build_resume_preamble(change_name, wt_path) -> str` function that lists files for the agent to re-read.
- [x] 1.2 The function checks file existence for: `openspec/changes/{name}/input.md`, `openspec/changes/{name}/design.md`, `tests/e2e/{name}.spec.ts`, and any `.claude/rules/*-conventions.md` file.
- [x] 1.3 Returns markdown with a "Context Restoration" header, numbered file list, and "Key reminders" section about exact design tokens.

## 2. Wire preamble into resume_change

- [x] 2.1 In `resume_change()` (~L2374), wrap the existing `task_desc = retry_ctx` with the preamble: `task_desc = _build_resume_preamble(change_name, wt_path) + "\n\n" + retry_ctx`.
- [x] 2.2 Update the log message to include both lengths: `"resuming %s with retry context (%d chars + %d preamble)"`.
- [x] 2.3 Ensure the preamble is ONLY added when `retry_ctx` is non-empty (initial resume without retry context shouldn't get preamble).

## 3. Test the preamble structure

- [x] 3.1 Manual test: verified with real minishop-run1 admin-products worktree — 728 char preamble, all 4 files found.
- [x] 3.2 Verified preamble returns empty string when worktree has no relevant files.
