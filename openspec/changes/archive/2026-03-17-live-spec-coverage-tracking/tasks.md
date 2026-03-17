## 1. Decompose skill — source_items instruction

- [x] 1.1 Add `source_items` array to the plan JSON schema in `.claude/skills/wt/decompose/SKILL.md` — format: `[{id: "SI-N", text: "...", change: "name"|null}]` [REQ: source-item-extraction-for-single-file-specs]
- [x] 1.2 Add instruction: "For single-file specs (no digest directory), generate a `source_items` array listing every identifiable spec item with an assigned change name or null if intentionally excluded. Omit `source_items` in digest mode." [REQ: source-item-extraction-for-single-file-specs]

## 2. Plan validation — source_items coverage check

- [x] 2.1 In `validate_plan()` (planner.py), when `digest_dir` is None and plan contains `source_items`: validate that every entry with a non-null `change` references an existing change name in the plan — produce errors for invalid references [REQ: source-item-extraction-for-single-file-specs]
- [x] 2.2 Emit warnings for `source_items` entries with `change: null` (intentional exclusions) [REQ: source-item-extraction-for-single-file-specs]
- [x] 2.3 Emit a warning if `source_items` is absent and `digest_dir` is None (no coverage tracking possible) [REQ: source-item-extraction-for-single-file-specs]

## 3. Coverage report — state-aware rendering

- [x] 3.1 Add optional `state_file: str | None` parameter to `generate_coverage_report()` (planner.py) [REQ: spec-coverage-report-generation]
- [x] 3.2 When `state_file` is provided, build a `change_name → status` lookup from state and render each requirement's status as MERGED/DISPATCHED/FAILED/PENDING instead of static COVERED [REQ: spec-coverage-report-generation]
- [x] 3.3 Preserve backward compatibility: when `state_file` is None, render existing COVERED/DEFERRED/UNCOVERED (no behavior change at plan validation time) [REQ: spec-coverage-report-generation]

## 4. Coverage report — single-file mode support

- [x] 4.1 Add `plan_path: str | None` parameter to `generate_coverage_report()` for reading `source_items` when `digest_dir` is absent [REQ: spec-coverage-report-generation]
- [x] 4.2 When rendering from `source_items`: use `SI-N` as ID, `text` as title, assigned change status from state, `EXCLUDED` for null-change entries [REQ: spec-coverage-report-generation]

## 5. Engine — terminal report regeneration

- [x] 5.1 In `_send_terminal_notifications()` (engine.py), call `generate_coverage_report()` with `state_file` before `final_coverage_check()` — this regenerates `spec-coverage-report.md` with live data [REQ: spec-coverage-report-generation]
- [x] 5.2 Pass `plan_path` (from state extras or well-known location `orchestration-plan.json`) to support single-file mode report generation [REQ: spec-coverage-report-generation]

## 6. Tests

- [x] 6.1 Unit test: `validate_plan()` with `source_items` — valid change refs pass, invalid refs error, null-change entries warn, missing `source_items` in non-digest mode warns [REQ: source-item-extraction-for-single-file-specs]
- [x] 6.2 Unit test: `generate_coverage_report()` with `state_file` — MERGED/FAILED statuses render correctly, backward compat without state_file preserved [REQ: spec-coverage-report-generation]
- [x] 6.3 Unit test: `generate_coverage_report()` from `source_items` — renders source items with statuses, EXCLUDED for null-change entries [REQ: spec-coverage-report-generation]

## Acceptance Criteria

- [x] AC-1: WHEN single-file spec is decomposed THEN plan contains `source_items` with every spec item mapped [REQ: source-item-extraction-for-single-file-specs]
- [x] AC-2: WHEN `source_items` entry has `change: null` THEN `validate_plan()` emits warning, not error [REQ: source-item-extraction-for-single-file-specs]
- [x] AC-3: WHEN orchestration completes THEN `spec-coverage-report.md` shows MERGED for merged changes, FAILED for failed changes [REQ: spec-coverage-report-generation]
- [x] AC-4: WHEN `generate_coverage_report()` called without `state_file` THEN output matches existing behavior (COVERED/DEFERRED/UNCOVERED) [REQ: spec-coverage-report-generation]
- [x] AC-5: WHEN non-digest plan with `source_items` reaches terminal state THEN coverage report renders source items with live statuses [REQ: spec-coverage-report-generation]
