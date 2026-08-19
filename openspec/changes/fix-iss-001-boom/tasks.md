## 1. Framework: resolve_project_name() fallback

- [ ] 1.1 In `lib/set_orch/paths.py`, change the `git rev-parse` failure branch in `resolve_project_name()` to return `os.path.basename(os.path.abspath(cwd)) or "_global"` instead of `"_global"` [REQ: detection-bridge-skips-malformed-findings]
- [ ] 1.2 Add a `logger.debug` call in the non-git branch logging the resolved basename name for diagnostics [REQ: detection-bridge-skips-malformed-findings]

## 2. Framework: DetectionBridge validation gate

- [ ] 2.1 In `lib/set_orch/issues/detector.py`, add a guard in `_scan_project()` after reading each finding: skip and log WARNING if `summary` is absent or empty [REQ: detection-bridge-skips-malformed-findings]
- [ ] 2.2 In `lib/set_orch/issues/detector.py`, add a guard: skip and log WARNING if `severity` is absent or empty [REQ: detection-bridge-skips-malformed-findings]

## 3. Tests

- [ ] 3.1 In `tests/unit/test_finding_detector_retry.py`, add a test that feeds `DetectionBridge` a finding with `summary=""` and asserts no issue is registered and a WARNING is logged [REQ: detection-bridge-skips-malformed-findings]
- [ ] 3.2 Add a test for a finding with `severity=""` (same assertions) [REQ: detection-bridge-skips-malformed-findings]
- [ ] 3.3 Add a test for a finding with empty `summary` AND `severity` both absent [REQ: detection-bridge-skips-malformed-findings]
- [ ] 3.4 Add or update a test confirming a finding with valid `summary` and `severity` but missing `change` and `discovered_at` is still registered normally [REQ: detection-bridge-skips-malformed-findings]
- [ ] 3.5 Add a unit test for `resolve_project_name()` covering a non-git path; assert result equals `os.path.basename(path)` not `"_global"` [REQ: detection-bridge-skips-malformed-findings]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN DetectionBridge._scan_project() encounters a finding where `summary` is absent or empty string THEN the finding SHALL NOT be passed to issue_manager.register() AND a WARNING log line SHALL be emitted naming the project and finding id [REQ: detection-bridge-skips-malformed-findings, scenario: finding-without-summary-is-skipped]
- [ ] AC-2: WHEN DetectionBridge._scan_project() encounters a finding where `severity` is absent or empty string THEN the finding SHALL NOT be passed to issue_manager.register() AND a WARNING log line SHALL be emitted [REQ: detection-bridge-skips-malformed-findings, scenario: finding-without-severity-is-skipped]
- [ ] AC-3: WHEN DetectionBridge._scan_project() encounters a finding with non-empty `summary` and non-empty `severity` THEN the finding SHALL be processed exactly as before AND missing optional fields (change, detail, discovered_at) SHALL NOT prevent registration [REQ: detection-bridge-skips-malformed-findings, scenario: finding-with-summary-and-severity-is-processed-normally]
