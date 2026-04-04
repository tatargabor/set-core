# Tasks

## 1. Core: gate retry context builder (engine.py)

- [x] 1.1 Add `_build_gate_retry_context(change, wt_path, e2e_output)` in `lib/set_orch/engine.py` that assembles a structured retry prompt with: role framing, git log summary, git diff stat, parsed test results, raw output, and original scope
- [x] 1.2 Add `_parse_e2e_summary(output)` helper in `lib/set_orch/engine.py` — framework-agnostic regex to extract pass/fail/flaky/skipped counts and failing test names from the summary section of test runner output (matches `N failed`, `N passed`, `[browser] › file:line › test name` patterns)
- [x] 1.3 Update `_recover_integration_e2e_failed()` in `lib/set_orch/engine.py` to call `_build_gate_retry_context()` instead of inline retry_ctx construction (lines 1038-1044)
- [x] 1.4 Update inline retry_ctx construction in `lib/set_orch/merger.py` `_run_integration_gates()` (lines 934-938) to also use `_build_gate_retry_context()` so both paths produce the same enriched context

## 2. Git context collection

- [x] 2.1 In `_build_gate_retry_context()`, run `git log --oneline main..HEAD` capped at 30 lines, with fallback if git fails (returns empty section, not crash)
- [x] 2.2 Run `git diff --stat main..HEAD` capped at 50 lines
- [x] 2.3 Include last commit message body (often contains agent's completion summary) via `git log -1 --format=%B`
