# run-history-archive Specification

## Purpose
TBD - created by archiving change run-history-and-phase-continuity. Update Purpose after archive.
## Requirements
### Requirement: Centralized lineage-aware path resolver
The framework SHALL introduce a single class `LineagePaths` in `lib/set_orch/paths.py` that owns every orchestration path previously hardcoded in scattered call sites (plan file, domains file, digest dir, event streams, state file, state-archive, coverage report, e2e manifest, directives, config, review-findings, review-learnings, artifacts dir, sentinel status, issues registry, worktree reflection). Every Python and Bash call site that reads or writes one of those paths SHALL resolve it through `LineagePaths` (or, for Bash, through equivalent helpers in `bin/set-common.sh`) — no hardcoded `os.path.join(..., "orchestration-plan.json")`, no literal `"set/orchestration/digest"` strings outside the resolver.

#### Scenario: Resolver returns lineage-specific path
- **WHEN** a caller asks for `LineagePaths(project, lineage_id="docs/spec-v1.md").plan_file()`
- **AND** a rotated `orchestration-plan-<v1-slug>.json` exists in the project root
- **THEN** the resolver SHALL return that rotated path
- **AND** the caller SHALL receive it without knowledge of the rename mechanics

#### Scenario: Resolver returns live path for live lineage
- **WHEN** a caller asks for `plan_file()` under the lineage that matches `state.spec_lineage_id`
- **THEN** the resolver SHALL return the live `orchestration-plan.json`
- **AND** NOT the `-<slug>.json` copy

#### Scenario: Bash helper mirrors Python resolver
- **WHEN** `bin/set-orchestrate` or any shell script under `bin/` / `lib/orchestration/*.sh` needs an orchestration path
- **THEN** the path SHALL come from `set-common.sh` helpers (`lineage_plan_file`, `lineage_digest_dir`, etc.) that mirror the Python resolver's contract
- **AND** the helpers SHALL NOT contain literal `orchestration-plan.json` / `set/orchestration/digest` strings elsewhere in the shell codebase

### Requirement: Hardcoded-path audit gate blocks archiving
The verify pipeline for this change SHALL run a ripgrep-based audit across `lib/`, `bin/`, `scripts/`, `web/src/` that searches for the 18 canonical orchestration-path patterns outside the resolver module. The gate SHALL FAIL (blocking archive) while any production code file still contains a direct literal match. The audit results SHALL be tracked in `migration-audit.md` in the change directory, with per-file checkboxes updated as migration progresses.

#### Scenario: Audit finds a residual literal
- **WHEN** the gate greps for `orchestration-state.json` across code files
- **AND** `lib/set_orch/some_module.py` still contains `open("orchestration-state.json")`
- **THEN** the gate SHALL report that file + line in its failure message
- **AND** `migration-audit.md`'s row for that file SHALL remain unchecked
- **AND** the change SHALL NOT be archivable until the literal is replaced by a `LineagePaths` call

#### Scenario: Audit passes
- **WHEN** every code file's literal orchestration-path references have been replaced by `LineagePaths` calls (or are confirmed as read-only constants marked `[~]`, or deleted marked `[/]`)
- **THEN** the gate SHALL pass
- **AND** `/opsx:archive` MAY proceed

#### Scenario: Non-code files excluded
- **WHEN** the audit runs
- **THEN** it SHALL NOT consider markdown documentation, YAML templates, or openspec artefacts
- **AND** those are handled by a separate (non-blocking) docs sweep after archiving

### Requirement: Event stream rotation on replan and sentinel-stop
The orchestrator SHALL rotate the project-level event streams (`orchestration-events.jsonl` and `orchestration-state-events.jsonl`) to `orchestration-events-cycle<N>.jsonl` and `orchestration-state-events-cycle<N>.jsonl` before a new replan cycle begins, and whenever the sentinel stops cleanly, so that each cycle's events are preserved as a separate file.

#### Scenario: Replan preserves previous cycle events
- **WHEN** the monitor loop triggers `_auto_replan_cycle` for cycle N
- **THEN** `_archive_completed_to_jsonl(state_file)` SHALL run first (already existing behaviour)
- **AND** `orchestration-events.jsonl` SHALL be renamed to `orchestration-events-cycle<N>.jsonl` and a fresh empty `orchestration-events.jsonl` created
- **AND** `orchestration-state-events.jsonl` SHALL be rotated the same way
- **AND** the rotation SHALL complete before the new plan is written

#### Scenario: Sentinel clean stop rotates the live stream
- **WHEN** the sentinel is stopped via `set-sentinel stop` or the manager `/sentinel/stop` endpoint
- **AND** the orchestration is not marked `done`
- **THEN** the live `orchestration-events.jsonl` SHALL be rotated to `orchestration-events-cycle<N>.jsonl` with N = next unused integer
- **AND** a new empty `orchestration-events.jsonl` SHALL be created so a subsequent sentinel start appends to a fresh file

#### Scenario: Rotation failure does not block replan
- **WHEN** rotation fails with an OSError (e.g., disk full or permission denied)
- **THEN** the failure SHALL be logged at WARNING with the source path and reason
- **AND** the replan SHALL continue as before (best-effort rotation, never a hard blocker)

### Requirement: Archived session summaries
The archive writer SHALL include a `session_summary` block on each entry it writes to `state-archive.jsonl`, capturing aggregate Claude-session metrics so the Tokens and LLM-calls APIs can render the archived change even after the worktree is cleaned up.

#### Scenario: session_summary fields
- **WHEN** `_archive_completed_to_jsonl` writes an entry for a change that had a worktree
- **THEN** the entry SHALL include a `session_summary` object with keys: `call_count` (int), `input_tokens` (int), `output_tokens` (int), `cache_read_tokens` (int), `cache_create_tokens` (int), `first_call_ts` (ISO-8601 string or null), `last_call_ts` (ISO-8601 string or null), `total_duration_ms` (int)
- **AND** the values SHALL be computed by scanning `~/.claude/projects/-<mangled-worktree>/*.jsonl` at archive time
- **AND** if the session dir is missing or empty, every field SHALL default to `0` / `null` without raising

#### Scenario: Legacy archive entries
- **WHEN** the archive reader encounters an entry that lacks `session_summary`
- **THEN** the entry SHALL be returned as-is
- **AND** the reader SHALL NOT invent zeros or synthesize a summary

### Requirement: Backfill migration for historic archive entries
A one-off migration step SHALL run on framework upgrade (idempotent, safe to re-run) that opens every project's `state-archive.jsonl`, inspects entries that lack `spec_lineage_id` or `phase`, and backfills them from the project's `orchestration-plan.json::input_path` and from prior live-state snapshots where available. After migration the archive reader SHALL NOT inject a fallback `phase = 0`; every entry SHALL carry either an attributed lineage + phase or be explicitly surfaced under a synthetic `__unknown__` lineage when attribution failed.

#### Scenario: Migration attributes legacy entries
- **WHEN** a pre-change project has 6 archive entries without `spec_lineage_id` or `phase`
- **AND** the project's `orchestration-plan.json` has `input_path = "docs/spec.md"`
- **AND** prior rotated state snapshots (or the plan itself) reveal that each archived change originally belonged to a particular phase
- **THEN** the migration SHALL rewrite the archive file in place so every entry carries `spec_lineage_id = "docs/spec.md"` and its recovered `phase`
- **AND** the migration SHALL record a `migrated_at` timestamp on each rewritten entry
- **AND** the migration SHALL NOT modify entries that already have `spec_lineage_id` (idempotency)

#### Scenario: Migration cannot recover attribution
- **WHEN** an archive entry lacks every piece of recoverable attribution (no project plan file, no prior snapshots)
- **THEN** the entry SHALL receive `spec_lineage_id = "__unknown__"` and `phase = null`
- **AND** the migration SHALL log a WARNING listing every unrecoverable entry so the operator can decide to purge or retain

#### Scenario: Current writer entries untouched
- **WHEN** the archive reader loads an entry already written with `spec_lineage_id` + `phase` by the current writer
- **THEN** those fields SHALL be returned unchanged
- **AND** no migration action SHALL fire on that entry

### Requirement: Rotated event concatenation for readers
Any API that reads the orchestration event streams SHALL concatenate all rotated cycle files in chronological order alongside the live file.

#### Scenario: Activity timeline reads all cycles
- **WHEN** the Activity timeline API is invoked
- **THEN** it SHALL read `orchestration-events-cycle<N>.jsonl` for every rotated N in ascending order
- **AND** then the live `orchestration-events.jsonl`
- **AND** it SHALL emit the union of spans from all files, ordered by timestamp

#### Scenario: LLM-calls API includes rotated events
- **WHEN** the `/api/<project>/llm-calls` endpoint is called
- **THEN** `_read_llm_call_events` SHALL scan every rotated cycle file plus the live file
- **AND** calls from different cycles SHALL be returned interleaved in timestamp order

### Requirement: Lineage tagging on all history records
Every new history artefact written by this change SHALL carry `spec_lineage_id` so downstream readers can filter by lineage without heuristics.

#### Scenario: Archive entry
- **WHEN** `_archive_completed_to_jsonl` writes an entry
- **THEN** the entry SHALL include `spec_lineage_id` sourced from `state.spec_lineage_id`

#### Scenario: Rotated event files
- **WHEN** `_rotate_event_streams` produces a new `orchestration-events-cycleN.jsonl`
- **THEN** the first line of the rotated file SHALL be a header event `{"event":"CYCLE_HEADER","spec_lineage_id":"<lineage>","plan_version":<V>,"sentinel_session_id":"<uuid>","rotated_at":"<iso>"}`
- **AND** readers SHALL use this header to resolve lineage for every subsequent event in the file that lacks an explicit lineage field

#### Scenario: Coverage history line
- **WHEN** `_append_coverage_history` writes a line
- **THEN** the JSON object SHALL include `spec_lineage_id`

#### Scenario: E2E manifest history line
- **WHEN** `_append_e2e_manifest_history` writes a line
- **THEN** the JSON object SHALL include `spec_lineage_id`

#### Scenario: Worktree history line
- **WHEN** `_append_worktree_history` writes a line
- **THEN** the JSON object SHALL include `spec_lineage_id`

### Requirement: Per-lineage plan and digest retention
When a sentinel session opens a new lineage or replan regenerates the decomposed digest, the framework SHALL preserve the prior lineage's plan and digest files before overwriting, so the operator can switch back to an earlier lineage and see its original decomposition, requirements, domain split, and test plan.

#### Scenario: Sentinel opens a second lineage
- **WHEN** the sentinel is started with `--spec docs/spec-v2.md` and a prior `orchestration-plan.json` on disk belongs to `docs/spec-v1.md`
- **THEN** before the new plan is written, the existing `orchestration-plan.json` SHALL be copied to `orchestration-plan-<v1-slug>.json` (slug derived from the lineage id, safe for filenames)
- **AND** the existing `orchestration-plan-domains.json` (if present) SHALL be copied to `orchestration-plan-domains-<v1-slug>.json`
- **AND** the existing `set/orchestration/digest/` SHALL be renamed to `set/orchestration/digest-<v1-slug>/`
- **AND** fresh empty `orchestration-plan.json` and `set/orchestration/digest/` SHALL be created for v2
- **AND** the renamed v1 artefacts SHALL remain in place until an explicit purge operation requests their removal

#### Scenario: Digest read honours lineage
- **WHEN** a consumer reads the project digest (planner, Digest tab API, coverage computation)
- **AND** the consumer is operating under a lineage id `<L>`
- **THEN** the consumer SHALL look for `set/orchestration/digest-<L-slug>/` first
- **AND** fall back to the live `set/orchestration/digest/` only when `L` matches `state.spec_lineage_id`
- **AND** SHALL NOT silently use the live digest for a non-matching lineage (returns an empty/uncovered response instead)

#### Scenario: Plan read honours lineage
- **WHEN** a consumer requests the plan for lineage `<L>`
- **THEN** the live `orchestration-plan.json` is used when `L` matches the live lineage
- **AND** `orchestration-plan-<L-slug>.json` is used otherwise
- **AND** if no lineage-specific plan file exists, the consumer reports the plan as unavailable for that lineage (it is not synthesised from other lineages)

### Requirement: Retained worktree history
When a worktree is cleaned up (renamed to `<path>.removed.<epoch>`), the framework SHALL append a JSON line to `worktrees-history.json` capturing the original path, renamed path, change name, and removal timestamp.

#### Scenario: Cleanup writes history
- **WHEN** `cleanup_worktree` renames a worktree to `.removed.<epoch>`
- **THEN** a JSON object `{ "change": "<name>", "original_path": "...", "removed_path": "....removed.<epoch>", "removed_at": "<iso>", "purged": false }` SHALL be appended to `<project>/worktrees-history.json`
- **AND** if the file does not exist it SHALL be created

#### Scenario: Purge is explicit
- **WHEN** the operator runs `set-close <change> --purge` OR the sentinel invokes the purge path explicitly
- **THEN** the `.removed.*` directory SHALL be deleted from disk
- **AND** the corresponding history entry's `purged` field SHALL be set to `true`
- **WHEN** `--purge` is NOT specified
- **THEN** the `.removed.*` directory SHALL remain on disk so historic session JSONLs stay readable

