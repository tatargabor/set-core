## 1. Profile Interface

- [x] 1.1 Add `get_forbidden_patterns() -> list` method to NullProfile in `lib/set_orch/profile_loader.py` returning empty list [REQ: nullprofile-shall-provide-get-forbidden-patterns-interface]
- [x] 1.2 Document the pattern dict format in NullProfile docstring: `{pattern: str, severity: "critical"|"warning", message: str, file_glob: str (optional)}` [REQ: lint-patterns-shall-come-from-profile-and-project-knowledge]

## 2. GateConfig Integration

- [x] 2.1 Add `lint: str = "run"` field to GateConfig dataclass in `lib/set_orch/gate_profiles.py` [REQ: lint-gate-shall-integrate-with-gate-profiles]
- [x] 2.2 Set lint defaults per change_type in BUILTIN_GATE_PROFILES: infrastructure="skip", schema="warn", foundational="run", feature="run", cleanup-before="warn", cleanup-after="skip" [REQ: lint-gate-shall-integrate-with-gate-profiles]
- [x] 2.3 Add lint to resolve_gate_config override chain (plugin, gate_hints, directives) [REQ: lint-gate-shall-integrate-with-gate-profiles]

## 3. Lint Gate Implementation

- [x] 3.1 Create `_load_forbidden_patterns(wt_path: str, profile) -> list[dict]` in `lib/set_orch/verifier.py` — merge profile.get_forbidden_patterns() + project-knowledge.yaml verification.forbidden_patterns [REQ: lint-patterns-shall-come-from-profile-and-project-knowledge]
- [x] 3.2 Create `_extract_added_lines(diff_output: str) -> list[tuple[str, int, str]]` — parse diff, return (file_path, line_number, line_content) for added lines only [REQ: lint-gate-shall-scan-diff-for-forbidden-patterns]
- [x] 3.3 Create `_execute_lint_gate(change_name: str, change: Change, wt_path: str, profile) -> GateResult` — load patterns, extract added lines, match each pattern, aggregate results [REQ: lint-gate-shall-scan-diff-for-forbidden-patterns]
- [x] 3.4 In _execute_lint_gate: for CRITICAL matches, return GateResult("fail") with retry_context listing matched file, line, pattern, and message [REQ: lint-gate-shall-scan-diff-for-forbidden-patterns, scenario: critical-pattern-match-blocks]
- [x] 3.5 In _execute_lint_gate: for WARNING-only matches, return GateResult("pass") with output listing warnings [REQ: lint-gate-shall-scan-diff-for-forbidden-patterns, scenario: warning-pattern-does-not-block]
- [x] 3.6 In _execute_lint_gate: if no patterns configured, return GateResult("pass") immediately [REQ: lint-gate-shall-scan-diff-for-forbidden-patterns, scenario: no-patterns-pass]
- [x] 3.7 Support optional `file_glob` in pattern dicts — only match against files matching the glob [REQ: lint-gate-shall-scan-diff-for-forbidden-patterns]

## 4. Pipeline Registration

- [x] 4.1 Register lint gate in handle_change_done GatePipeline, after test_files and before review [REQ: lint-gate-shall-scan-diff-for-forbidden-patterns]
- [x] 4.2 Pass profile to _execute_lint_gate lambda in pipeline registration [REQ: lint-patterns-shall-come-from-profile-and-project-knowledge]

## 5. Tests

- [x] 5.1 Unit test: CRITICAL pattern match → gate fail with retry_context containing file/line/message [REQ: lint-gate-shall-scan-diff-for-forbidden-patterns, scenario: critical-pattern-match-blocks]
- [x] 5.2 Unit test: WARNING pattern match → gate pass with output containing warning [REQ: lint-gate-shall-scan-diff-for-forbidden-patterns, scenario: warning-pattern-does-not-block]
- [x] 5.3 Unit test: no matches → pass [REQ: lint-gate-shall-scan-diff-for-forbidden-patterns, scenario: no-matches-pass]
- [x] 5.4 Unit test: no patterns → pass [REQ: lint-gate-shall-scan-diff-for-forbidden-patterns, scenario: no-patterns-pass]
- [x] 5.5 Unit test: file_glob filtering — pattern with file_glob="*.ts" does not match .py files [REQ: lint-gate-shall-scan-diff-for-forbidden-patterns]
- [x] 5.6 Unit test: pattern source merging — profile + project-knowledge patterns both included [REQ: lint-patterns-shall-come-from-profile-and-project-knowledge]
- [x] 5.7 Run existing tests: `python -m pytest tests/test_gate_profiles.py -x` — must pass with new lint field [REQ: lint-gate-shall-integrate-with-gate-profiles]
