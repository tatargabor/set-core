# Tasks

## Test Infrastructure Detection (TP-1)

- [x] Add `detect_test_infra()` function that scans target project: vitest/jest config, `*.test.*` count, package.json test script, helper dirs. Returns JSON `{framework, config_exists, test_file_count, has_helpers, test_command}`.
- [x] Call `detect_test_infra()` at orchestrator start (in `cmd_plan`) and store results for planner context injection.

## test_command Auto-Detection (VG-3)

- [x] Add `auto_detect_test_command()` function: reads package.json, checks scripts for `test` → `test:unit` → `test:ci`, detects package manager from lockfile (npm/yarn/pnpm). Returns command string or empty.
- [x] Integrate into directive resolution: if `test_command` is empty after directive parsing, call `auto_detect_test_command()`. Log result.

## Planner Prompt: Test-Aware (TP-2, TP-3, TP-4)

- [x] Inject test infra scan results into the plan decomposition prompt context section.
- [x] Add planner prompt rules: "Every change scope MUST include test requirements", "Security changes must include tenant isolation and auth guard tests".
- [x] Add planner prompt rule for missing infra: "If no test infrastructure, first change MUST be test-infrastructure-setup with all others depending on it".

## Model Tiering (MT-1 through MT-5)

- [x] Modify `run_claude()` to accept optional model parameter. Map `haiku`/`sonnet`/`opus` to full model IDs. Pass `--model <id>` to claude CLI when set.
- [x] Add `summarize_model` and `review_model` directives to `parse_directives()` / `resolve_directives()` with validation (must be haiku|sonnet|opus).
- [x] Update `summarize_spec()` to use `summarize_model` directive (default: haiku).
- [x] Hardcode `cmd_plan()` decomposition call to use opus model explicitly.

## Verify Gate (VG-1, VG-2, VG-5)

- [x] Add `run_tests_in_worktree()` function: `cd $wt_path && timeout $test_timeout $test_command`, captures exit code + output (truncated to 2000 chars).
- [x] Add `verify-failed` and `verifying` to valid change statuses.
- [x] Modify `handle_change_done()`: before merge, set status to `verifying`, call `run_tests_in_worktree()`. On pass → proceed to merge. On fail → restart Ralph with test failure context (respecting `verify_retried` flag and `max_verify_retries`).
- [x] Store test results in change state: `test_result`, `test_output` fields.
- [x] Add `test_timeout` directive (default: 300s) and `max_verify_retries` directive (default: 1).

## LLM Code Review Gate (VG-4)

- [x] Add `review_change()` function: generates git diff of change branch vs target, sends to Claude with review prompt using `review_model`.
- [x] Review prompt template: include diff, original scope, check for security gaps, missing auth, tenant isolation.
- [x] Parse review output for "CRITICAL" severity — if found, treat as test failure (retry Ralph).
- [x] Integrate into `handle_change_done()` flow: tests pass → review (if `review_before_merge: true`) → merge.
- [x] Add `review_before_merge` directive (default: false).

## Status and Logging

- [x] Update `cmd_status()` to show verify gate info: test result per change, review status, verify-failed count.
- [x] Log verify gate events: test start/pass/fail, review start/pass/critical, retry dispatch.
