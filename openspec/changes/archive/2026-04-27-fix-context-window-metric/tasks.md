# Tasks

## 1. Helper: per-call peak from session JSONL

- [ ] 1.1 Add `peak_per_call_context()` method to `UsageCalculator` in `gui/usage_calculator.py` that scans iterated JSONL files in the time window and returns `max(input_tokens + cache_read_input_tokens + cache_creation_input_tokens)` per parsed line; also return the call count and the peak's breakdown for debug logging [REQ: context-tokens-captured-at-first-iteration-completion]
- [ ] 1.2 Add a unit test for `peak_per_call_context()` covering: empty input → 0; single call → its own sum; multi-call → max not last; mixed sessions per project_dir filter [REQ: context-tokens-captured-at-first-iteration-completion]
- [ ] 1.3 Surface the new value in `bin/set-usage` `--format json` output as `peak_per_call_context` (only when computed; omit when 0/unavailable) [REQ: context-tokens-captured-at-first-iteration-completion]

## 2. Loop state writer captures peak per iteration

- [ ] 2.1 Update `lib/loop/state.sh` `get_current_tokens()` (and the iteration-finalize JSON merge near line 198) to include `peak_context_tokens` per iteration entry, sourced from the new `set-usage --format json` field [REQ: context-tokens-captured-at-loop-completion]
- [ ] 2.2 Update the iteration aggregation jq pipeline so loop-state.json carries `peak_context_tokens` per `iterations[]` entry; do not aggregate to a `total_*` (peak is not summable) [REQ: context-tokens-captured-at-loop-completion]
- [ ] 2.3 Add a logger.debug line that prints peak_context_tokens at each iteration finalize, with breakdown (PID, iteration index, peak value) [REQ: context-tokens-captured-at-loop-completion]

## 3. Verifier rewrite — peak-based formulas

- [ ] 3.1 Rewrite `_capture_context_tokens_start` in `lib/set_orch/verifier.py` to use `iter1.get("peak_context_tokens")` instead of `cache_create_tokens`. If absent, write nothing (no fallback). Update the log message to say "peak context per call" [REQ: context-tokens-captured-at-first-iteration-completion]
- [ ] 3.2 Rewrite `_capture_context_tokens_end` in `lib/set_orch/verifier.py` to compute `max(it.get("peak_context_tokens", 0) for it in iterations)`. Remove the `total_cache_create` fallback completely [REQ: context-tokens-captured-at-loop-completion]
- [ ] 3.3 Update the WARNING/INFO threshold log in `_capture_context_tokens_end` so the percentage is computed from the now-correct peak (formula stays `peak/cw*100`, but the input is correct) [REQ: context-tokens-captured-at-loop-completion]
- [ ] 3.4 Add a test that feeds a synthetic `loop_state` dict with multiple iterations, each carrying `peak_context_tokens`, and asserts `context_tokens_end` equals the max — never a sum [REQ: end-tokens-never-derived-from-cumulative-cache_create]

## 4. State serializer exposes context_window_size

- [ ] 4.1 Find the orchestration state → API JSON serializer (likely `lib/set_orch/state.py` or `lib/set_orch/api/`); for each change object, add a `context_window_size` field derived from `_context_window_for_model(change.model)` [REQ: context-window-size-is-dynamic-per-model]
- [ ] 4.2 Move `_context_window_for_model` to a location importable by both verifier.py and the serializer (or just import from verifier.py — confirm there's no circular import) [REQ: context-window-size-is-dynamic-per-model]
- [ ] 4.3 Add a test asserting `context_window_size` is 1_000_000 for `model="opus"`, 1_000_000 for `model="claude-opus-4-6"`, 200_000 for any model containing `[200k]` [REQ: context-window-size-is-dynamic-per-model]

## 5. Frontend uses dynamic window

- [ ] 5.1 Add `context_window_size?: number` to the change type in `web/src/lib/api.ts` (next to `context_tokens_start`/`context_tokens_end`) [REQ: context-window-size-is-dynamic-per-model]
- [ ] 5.2 In `web/src/components/ChangeTable.tsx` lines 99, 106, 201: replace every `200_000` literal with `(c.context_window_size ?? 1_000_000)`. Fall back to 1M (current default), never 200K [REQ: context-window-size-is-dynamic-per-model]
- [ ] 5.3 Verify no other frontend file divides by `200_000` for context calculations: `grep -rn "200_000\|200000" web/src --include="*.tsx" --include="*.ts"` and fix any other hits [REQ: context-window-size-is-dynamic-per-model]
- [ ] 5.4 Update the title tooltip in ChangeTable that may also reference the legacy threshold [REQ: set-web-change-list-shows-context-metrics-with-dynamic-window]
- [ ] 5.5 Run `pnpm build` in `web/` so port 7400 serves the updated bundle [REQ: set-web-change-list-shows-context-metrics-with-dynamic-window]

## 6. Run-report template cleanup

- [ ] 6.1 Grep for the literal "CONTEXT WINDOW OVERFLOW" string across `lib/`, `bin/`, `templates/`, `.claude/`, and `lib/set_orch/templates/`; identify the source [REQ: context-tokens-captured-at-loop-completion]
- [ ] 6.2 If the source is found, update its threshold check to use the new peak-based metric and the dynamic window. Reword the finding text to refer to "peak per-call context" instead of cumulative cache writes [REQ: context-tokens-captured-at-loop-completion]
- [ ] 6.3 If the source is not found in step 6.1, add a TODO note in `tasks.md` and open a follow-up — do not block this change on it [REQ: context-tokens-captured-at-loop-completion]

## 7. Verification on real run data

- [ ] 7.1 Run `python3 -c "..."` against `craftbrew-run-20260408-1014`'s session JSONL files (already explored during root-cause) and assert the new helper returns ~150K for both `auth-and-accounts` and `product-catalog`, not the cumulative 1.4M / 2.4M [REQ: end-tokens-never-derived-from-cumulative-cache_create]
- [ ] 7.2 Manually trigger `_capture_context_tokens_end` for one of those changes (or rerun a verify step) and confirm `orchestration-state.json` now has `context_tokens_end` ≈ 150K [REQ: end-tokens-never-derived-from-cumulative-cache_create]
- [ ] 7.3 Open the dashboard at port 7400, locate one of those changes, confirm the badge reads ~15% (not 141%/241%) [REQ: frontend-uses-dynamic-window-from-api]
- [ ] 7.4 Run the web E2E test suite (`cd web && E2E_PROJECT=craftbrew-run-20260408-1014 pnpm test:e2e`) to confirm no other tab broke from the api.ts type addition [REQ: set-web-change-list-shows-context-metrics-with-dynamic-window]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN a change's loop completes its first iteration AND the session JSONL files for iteration 1 are readable THEN the change's orchestration state entry has `context_tokens_start = max(input + cache_read + cache_create)` per individual API call across iteration 1 [REQ: context-tokens-captured-at-first-iteration-completion, scenario: start-tokens-recorded-after-iteration-1-with-peak-data-available]
- [ ] AC-2: WHEN session JSONL files for iteration 1 are missing or unreadable THEN `context_tokens_start` is not written to state [REQ: context-tokens-captured-at-first-iteration-completion, scenario: start-tokens-absent-if-peak-data-unavailable]
- [ ] AC-3: WHEN a change's loop completes AND session JSONL files exist for at least one iteration THEN the change's state entry has `context_tokens_end = max(input + cache_read + cache_create)` per call across all iterations [REQ: context-tokens-captured-at-loop-completion, scenario: end-tokens-recorded-as-peak-per-call-context]
- [ ] AC-4: WHEN inspecting how `context_tokens_end` is computed THEN the formula MUST NOT use `total_cache_create`, `total_input_tokens + total_cache_create`, or `max(per-iteration cache_create_tokens)` [REQ: end-tokens-never-derived-from-cumulative-cache_create, scenario: end-tokens-never-derived-from-cumulative-cache_create]
- [ ] AC-5: WHEN no session JSONL files are available for any iteration THEN `context_tokens_end` is not written to state [REQ: context-tokens-captured-at-loop-completion, scenario: end-tokens-absent-for-runs-without-session-jsonl-data]
- [ ] AC-6: WHEN a change runs with `model = "opus"` (or sonnet/haiku/claude-opus-4-6) THEN orchestration state has `context_window_size = 1_000_000` [REQ: context-window-size-is-dynamic-per-model, scenario: 1m-window-for-claude-4-x-models-by-default]
- [ ] AC-7: WHEN a change runs with a model name containing `[200k]` THEN orchestration state has `context_window_size = 200_000` [REQ: context-window-size-is-dynamic-per-model, scenario: 200k-window-for-explicit-legacy-suffix]
- [ ] AC-8: WHEN ChangeTable renders a row with `context_tokens_end = 150_000` and `context_window_size = 1_000_000` THEN displayed utilization is `15%`, not `75%`, and no `200_000` literal appears [REQ: context-window-size-is-dynamic-per-model, scenario: frontend-uses-dynamic-window-from-api]
- [ ] AC-9: WHEN a change has `context_tokens_end = 150_000` and `context_window_size = 1_000_000` THEN the change list shows `ctx: 150K (15%)` [REQ: set-web-change-list-shows-context-metrics-with-dynamic-window, scenario: context-metric-displayed-for-completed-change]
- [ ] AC-10: WHEN a change has `context_tokens_start = 40_000`, `context_tokens_end = 150_000`, `context_window_size = 1_000_000` THEN the list shows `ctx: 40K → 150K (15%)` [REQ: set-web-change-list-shows-context-metrics-with-dynamic-window, scenario: context-metric-shows-start-end-when-both-available]
- [ ] AC-11: WHEN a change has no `context_tokens_end` THEN no `ctx` indicator is shown and no error appears [REQ: set-web-change-list-shows-context-metrics-with-dynamic-window, scenario: context-metric-absent-for-changes-without-data]
- [ ] AC-12: WHEN `context_tokens_end / context_window_size >= 0.80` THEN the metric is displayed with a warning color, computed against the dynamic window [REQ: set-web-change-list-shows-context-metrics-with-dynamic-window, scenario: high-context-utilization-is-visually-highlighted]
