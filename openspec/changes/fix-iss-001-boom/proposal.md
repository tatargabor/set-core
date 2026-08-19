## Why

Non-git project directories (e.g. scratchpad/status-probe) fall back to `"_global"` in `resolve_project_name()`, causing them to share the global sentinel runtime directory with every other non-git directory. A stale test finding (`F001 "boom"`) already present in the global sentinel was picked up by `DetectionBridge` and registered as ISS-001 against the `status-probe` environment — even though `probe.py` is functioning correctly. The false positive triggered an investigation session consuming agent budget unnecessarily.

## What Changes

- `resolve_project_name()` in `lib/set_orch/paths.py`: use the directory's basename as the fallback project name for non-git paths instead of hardcoding `"_global"`. Reserve `"_global"` only when `project_path` is `None` or when `os.getcwd()` itself fails.
- `DetectionBridge._scan_project()`: add a warning log when a finding is missing required fields (`change`, `discovered_at`), and skip registering issues for findings whose `severity` is absent or whose `summary` is empty. This prevents bare-minimum test artifacts from creating real issues.
- Global sentinel cleanup: document that `_global` findings.json is shared state and should not contain ad-hoc test findings (no code change needed — process note in `docs/guide/sentinel.md`).

## Capabilities

### New Capabilities

*(none — this is a bug-fix-only change)*

### Modified Capabilities

- `sentinel-findings`: The requirement that findings SHALL have `discovered_at`, `change`, `summary` and `detail` fields will be enforced at the detection layer, not just at write time. The delta spec adds a validation scenario to `DetectionBridge`.

## Impact

- `lib/set_orch/paths.py`: one-line change to `resolve_project_name()` fallback
- `lib/set_orch/issues/detector.py`: add field-presence guard in `_scan_project()`
- `tests/unit/test_finding_detector_retry.py`: add coverage for malformed finding skip
- No API or schema change; existing persisted sentinel data is unaffected

## Fix Target

- **Target:** both
- **Reasoning:** The immediate trigger (stale "boom" finding in global sentinel) is consumer-local and already self-resolved (finding is now `"pipeline"` — the detector will never rescan it). But the root cause — non-git directories silently sharing `"_global"` runtime, allowing cross-project finding contamination — is a framework defect in `resolve_project_name()` and `DetectionBridge`. Without the framework fix, any future scratchpad or temp directory would repeat the same false-positive pattern.
