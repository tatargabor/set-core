## 1. Helper for tail + marker extraction

- [ ] 1.1 Add private helper `_build_failure_tail(e2e_output: str, max_lines: int = 80, hard_cap: int = 500) -> str` in `modules/web/set_project_web/gates.py`. Returns a formatted string with two sections: `## Crash markers detected` (matched lines with original line numbers, omitted if no matches) and `## Stdout/stderr tail (last N lines)` (last N lines verbatim, where N = min(max_lines, total_lines)). [REQ: Unparseable-failure retry_context includes a stdout/stderr tail]
- [ ] 1.2 Crash-marker patterns: `Error:`, `Traceback`, `webServer`, `Killed`, `OOM`, `assert` (case-insensitive substring match); store as a module-level constant `_CRASH_MARKERS` so future profiles can reference if needed. Format matched lines as `L{n}: {line}` where `{n}` is 1-indexed. [REQ: Crash-marker lines surface separately]
- [ ] 1.3 Hard-cap the configurable max_lines at 500 to prevent absurd `gate_overrides` settings from blowing context. Log at WARN if `max_lines > 500` is requested. [REQ: Unparseable-failure retry_context includes a stdout/stderr tail]

## 2. Wire into the unparseable-failure branch

- [ ] 2.1 In the `if not wt_failures:` branch (around line 1613-1648 of `gates.py`), read `gate_overrides.e2e.failure_tail_lines` (default 80) from the gate config / state. [REQ: Unparseable-failure retry_context includes a stdout/stderr tail]
- [ ] 2.2 Build the tail via `_build_failure_tail(e2e_output, max_lines=<resolved>)` and append it to the existing `retry_ctx` after the orientation paragraph and any self-heal suffix, separated by a blank line. [REQ: Existing orientation paragraph and self-heal note are preserved]
- [ ] 2.3 Verify the parseable-failure-list path is UNTOUCHED — no behavior change when `wt_failures` is non-empty. [REQ: Unparseable-failure retry_context includes a stdout/stderr tail]

## 3. Tests

- [ ] 3.1 Unit test `test_build_failure_tail_short_output_returned_whole`: 30-line input, max_lines=80 → output contains all 30 lines under heading `## Stdout/stderr tail (last 30 lines)`. [REQ: Unparseable-failure retry_context includes a stdout/stderr tail, scenario: short-output-included-whole]
- [ ] 3.2 Unit test `test_build_failure_tail_truncates_to_max_lines`: 200-line input, max_lines=80 → tail section contains exactly 80 lines (the last 80 of input), heading reads `(last 80 lines)`. [REQ: Unparseable-failure retry_context includes a stdout/stderr tail, scenario: crash-with-empty-failure-list-tail-included]
- [ ] 3.3 Unit test `test_build_failure_tail_marker_outside_window_surfaced`: 1000-line input where `Error:` appears on line 12, max_lines=80 → output includes `## Crash markers detected` section with `L12: ...Error:...`, AND `## Stdout/stderr tail (last 80 lines)` section with lines 921-1000. [REQ: Crash-marker lines surface separately, scenario: marker-outside-the-tail-window-is-still-surfaced]
- [ ] 3.4 Unit test `test_build_failure_tail_no_markers_section_omitted`: input with no crash markers → output has tail section but NO marker section. [REQ: Crash-marker lines surface separately, scenario: no-markers-section-omitted]
- [ ] 3.5 Unit test `test_build_failure_tail_hard_cap_at_500`: max_lines=10000 requested → output capped at 500 lines, WARN log fires. [REQ: Unparseable-failure retry_context includes a stdout/stderr tail]
- [ ] 3.6 Unit test for the wired call site `test_e2e_gate_unparseable_failure_includes_tail`: mock `e2e_cmd_result.exit_code=1`, mock `_extract_e2e_failure_ids` returning `[]`, mock `e2e_output` with a stack trace → assert returned `GateResult.retry_context` contains the orientation paragraph AND the new tail section. [REQ: Existing orientation paragraph and self-heal note are preserved, scenario: orientation-paragraph-stays-at-top]
- [ ] 3.7 Regression test `test_e2e_gate_parseable_failure_path_unchanged`: when `_extract_e2e_failure_ids` returns non-empty, retry_context does NOT contain `## Stdout/stderr tail` heading. [REQ: Unparseable-failure retry_context includes a stdout/stderr tail]

## 4. Live verification

- [ ] 4.1 After landing this change, observe the next time a project hits the unparseable-failure path (look for a retry_context journal entry with `## Stdout/stderr tail` heading). Confirm the agent's next iteration immediately addresses the crash without first reading trace artifacts. [REQ: Unparseable-failure retry_context includes a stdout/stderr tail]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN exit_code=1 and failure list empty THEN retry_context contains `## Stdout/stderr tail (last 80 lines)` heading and the last 80 lines [REQ: Unparseable-failure retry_context includes a stdout/stderr tail, scenario: crash-with-empty-failure-list-tail-included]
- [ ] AC-2: WHEN e2e_output is shorter than 80 lines THEN entire output appears with heading `(last <N> lines)` [REQ: Unparseable-failure retry_context includes a stdout/stderr tail, scenario: short-output-included-whole]
- [ ] AC-3: WHEN gate_overrides.e2e.failure_tail_lines=200 THEN tail contains up to 200 lines [REQ: Unparseable-failure retry_context includes a stdout/stderr tail, scenario: override-via-gate_overrides]
- [ ] AC-4: WHEN a marker appears on line 12 and tail covers lines 921-1000 THEN the marker section includes `L12: ...` and tail covers 921-1000 [REQ: Crash-marker lines surface separately, scenario: marker-outside-the-tail-window-is-still-surfaced]
- [ ] AC-5: WHEN no markers present THEN marker section is omitted but tail is still present [REQ: Crash-marker lines surface separately, scenario: no-markers-section-omitted]
- [ ] AC-6: WHEN unparseable-failure path with no self-heal THEN orientation paragraph is the FIRST text in retry_context [REQ: Existing orientation paragraph and self-heal note are preserved, scenario: orientation-paragraph-stays-at-top]
- [ ] AC-7: WHEN self_heal_pkg is set THEN self-heal suffix appears immediately after orientation, before marker/tail sections [REQ: Existing orientation paragraph and self-heal note are preserved, scenario: self-heal-note-stays-inline-with-orientation]
