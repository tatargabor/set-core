## Why

The orchestration pipeline has two input modes: digest mode (multi-file spec → `requirements.json` with REQ-IDs) and single-file mode (one markdown spec → `orchestration-plan.json` with `roadmap_item` free text). Digest mode has full lifecycle coverage tracking (`coverage.json`, `update_coverage_status()`, `final_coverage_check()`). Single-file mode has **zero coverage tracking** — there is no structured link between the original spec items and the plan changes, and no way to detect what was omitted or completed.

Additionally, the human-readable `spec-coverage-report.md` is generated once during `validate_plan()` and never updated as changes are merged. It stays frozen at "COVERED" even after items are merged — diverging from the live `coverage.json` data.

## What Changes

- **`planner.py`**: `generate_coverage_report()` gains a `state_file` parameter and reads change statuses to render MERGED/DISPATCHED/FAILED alongside COVERED/DEFERRED/UNCOVERED. Called both at plan validation time and at final summary time (regenerate with live data).
- **`planner.py`**: New `extract_source_items()` function for single-file mode — parses the plan's `roadmap_item` fields into a structured `source_items[]` list stored in the plan JSON, enabling coverage validation without a digest.
- **`engine.py`**: After completion (all changes merged/failed), calls `regenerate_coverage_report()` to produce an up-to-date `spec-coverage-report.md` reflecting final statuses.

## Capabilities

### New Capabilities
- `single-file-spec-coverage`: For non-digest plans, the decompose output includes a `source_items` array mapping each original spec item to its assigned change, enabling coverage gap detection without a full digest pipeline.

### Modified Capabilities
- `spec-coverage-report`: The report now reflects live change statuses (MERGED, DISPATCHED, FAILED, PENDING) instead of the static COVERED/DEFERRED/UNCOVERED from plan validation time. Regenerated at orchestration completion.

## Impact

- `lib/set_orch/planner.py`: `generate_coverage_report()` — add state-aware status rendering + new `extract_source_items()` function
- `lib/set_orch/engine.py`: `_on_all_complete()` or equivalent — trigger report regeneration
- `.claude/skills/wt/decompose/SKILL.md`: Add `source_items` array to plan schema for single-file mode
- No breaking changes — existing digest-mode coverage tracking is unaffected
