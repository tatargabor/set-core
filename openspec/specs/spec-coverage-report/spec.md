# Spec Coverage Report Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Spec coverage report generation
`generate_coverage_report()` SHALL produce a markdown report mapping requirements (or source items) to changes with their current lifecycle status. The report SHALL be regenerated at orchestration terminal state to reflect final statuses.

#### Scenario: State-aware report in digest mode
- **WHEN** `generate_coverage_report()` is called with a `state_file` parameter
- **THEN** each requirement's status SHALL reflect the owning change's status from state: MERGED, DISPATCHED, FAILED, or PENDING
- **AND** the status SHALL replace the static COVERED label used at plan validation time
- **AND** DEFERRED and UNCOVERED items SHALL remain unchanged (they have no owning change)

#### Scenario: Report from source items in single-file mode
- **WHEN** `generate_coverage_report()` is called without `digest_dir` but with a plan containing `source_items`
- **THEN** the report SHALL render source items instead of digest requirements
- **AND** each source item SHALL show its assigned change and that change's status
- **AND** items with `change: null` SHALL show as EXCLUDED

#### Scenario: Report regenerated at terminal state
- **WHEN** the orchestration reaches a terminal state (done, time_limit, total_failure, dep_blocked, replan_limit, replan_exhausted)
- **THEN** `_send_terminal_notifications()` SHALL call report regeneration before sending the summary email
- **AND** the regenerated report SHALL overwrite the initial plan-time report at `set/orchestration/spec-coverage-report.md`

#### Scenario: Backward compatibility when state_file is not provided
- **WHEN** `generate_coverage_report()` is called without `state_file` (e.g., during plan validation)
- **THEN** the function SHALL produce the existing static COVERED/DEFERRED/UNCOVERED report
- **AND** no error is raised

### In scope
- `generate_coverage_report()` state-aware rendering
- `generate_coverage_report()` single-file mode (source_items)
- Engine terminal state trigger for report regeneration
- Summary line with MERGED/FAILED/PENDING counts

### Out of scope
- Per-merge incremental report updates (terminal regeneration is sufficient)
- Report format changes beyond status column (table structure stays the same)
- Email content changes (email already uses `final_coverage_check()` output)
## Requirements
### Requirement: Coverage denominator is the lineage's own spec
Coverage for a lineage SHALL be computed against the set of requirements defined in THAT lineage's input spec (the file referenced by its `spec_lineage_id`), not against the union of all project history. If a lineage's spec defines N requirements, the coverage denominator is N — regardless of how much code exists on disk from previous lineages.

#### Scenario: v2 delivers a single new screen on top of v1
- **WHEN** v1 lineage merged 50 changes covering 120 requirements
- **AND** v2 lineage's spec declares exactly 3 new requirements for a single new screen
- **AND** v2 merges 1 change that satisfies all 3 v2 requirements
- **THEN** v2's coverage SHALL report 3/3 = 100%
- **AND** v2 coverage SHALL NOT include the 120 v1 requirements in its denominator
- **AND** v1 coverage, viewed separately via the lineage selector, SHALL continue to report 120/120 against its own spec

#### Scenario: Pre-existing code does not pre-fill coverage
- **WHEN** v1 delivered an `/admin` page and v2's spec also references REQ-ADMIN-001 (identical wording)
- **AND** the `/admin` page code is already present on disk, carried over from v1
- **AND** no v2 change has touched REQ-ADMIN-001 yet
- **THEN** v2 coverage SHALL report REQ-ADMIN-001 as `uncovered`
- **AND** the Digest view SHALL NOT auto-mark the requirement as satisfied based on filesystem inspection

#### Scenario: Lineage spec defines subset of prior spec
- **WHEN** v1's spec defined REQs A, B, C and v2's spec defines only B (because v2 is a focused follow-up)
- **THEN** v2 coverage denominator is `{B}` (size 1)
- **AND** A and C are out of scope for v2 and SHALL NOT appear in v2's coverage response at all

### Requirement: Coverage history append on every merge
When the coverage report (`spec-coverage-report.md`) is regenerated after a successful merge, the generator SHALL also append a JSON line to `spec-coverage-history.jsonl` in the project root, capturing which change merged which REQs at which timestamp and under which lineage.

#### Scenario: Merge regenerates coverage
- **WHEN** a change named "foundation-setup" under lineage `docs/spec-v1.md` merges and covers REQ-FOUND-001, REQ-FOUND-002
- **AND** the framework regenerates `spec-coverage-report.md`
- **THEN** a JSON line `{ "change": "foundation-setup", "spec_lineage_id": "docs/spec-v1.md", "plan_version": <V>, "sentinel_session_id": <UUID>, "merged_at": "<iso>", "reqs": ["REQ-FOUND-001", "REQ-FOUND-002"] }` SHALL be appended to `spec-coverage-history.jsonl`
- **AND** the existing `spec-coverage-report.md` regeneration SHALL continue unchanged

#### Scenario: Replan does not wipe history
- **WHEN** replan drops REQ-FOUND-* from the current plan's coverage surface
- **THEN** `spec-coverage-history.jsonl` entries MUST remain intact
- **AND** subsequent coverage reads under the v1 lineage for REQ-FOUND-001 SHALL still resolve to "merged by foundation-setup (archived, <iso>)"

### Requirement: Coverage history carries lineage
Every `spec-coverage-history.jsonl` line SHALL carry `spec_lineage_id`, and the Digest/Reqs endpoint SHALL accept `?lineage=<id>` and return coverage computed only against records tagged with that lineage AND against that lineage's own spec scope (per the "denominator" requirement above).

#### Scenario: v1 coverage snapshot while v2 runs
- **WHEN** the client calls `GET /api/<project>/digest?lineage=docs/spec-v1.md`
- **THEN** the Reqs / AC / E2E breakdown SHALL only consider v1-tagged changes and v1-tagged history lines
- **AND** the denominator SHALL be the set of REQs declared in v1's own spec file

### Requirement: Digest attribution uses history
The Digest/Reqs API response SHALL, for every merged REQ under the requested lineage, carry the identity of the change that merged it and the merge timestamp, sourced from `spec-coverage-history.jsonl`.

#### Scenario: REQ covered by an archived change within the lineage
- **WHEN** the Digest panel requests REQ-FOUND-001 under lineage v1
- **AND** the REQ does not appear under any CURRENT v1-plan change (replan dropped it)
- **AND** `spec-coverage-history.jsonl` contains a v1-tagged line attributing REQ-FOUND-001 to "foundation-setup"
- **THEN** the API response SHALL include `merged_by = "foundation-setup"`, `merged_by_archived = true`, `merged_at = <iso>`

#### Scenario: REQ not in the current lineage's spec
- **WHEN** REQ-V1-SPECIFIC is in v1's spec but NOT in v2's spec
- **AND** the client requests `GET /api/<project>/digest?lineage=v2`
- **THEN** REQ-V1-SPECIFIC SHALL NOT appear in the v2 response at all (not even as "uncovered")
- **AND** the v2 coverage percentage SHALL not be affected by REQ-V1-SPECIFIC's existence

