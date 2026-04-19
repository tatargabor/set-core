## 0. Centralized lineage path resolver (pre-work for every other workstream)

- [x] 0.1 Design `LineagePaths` class in `lib/set_orch/paths.py` — accepts `project_path: str, lineage_id: Optional[str] = None`. Every orchestration path property is read-only and either returns a lineage-specific file/dir (when `lineage_id` differs from the live lineage) or the live path. Falls back to live when no lineage-specific file exists, logging at DEBUG. [REQ: centralized-lineage-aware-path-resolver]
- [x] 0.2 Implement properties covering every pattern in `migration-audit.md` Phase 1: `plan_file`, `plan_domains_file`, `events_file`, `rotated_event_files`, `state_events_file`, `state_file`, `state_archive`, `digest_dir`, `coverage_report`, `coverage_history`, `e2e_manifest_for_worktree`, `e2e_manifest_history`, `supervisor_status`, `supervisor_status_history`, `issues_registry`, `reflection_for_worktree`, `directives_file`, `config_yaml`, `review_learnings`, `review_findings`, `artifacts_dir_for_change`, `specs_archive_dir`, `worktrees_history`. [REQ: centralized-lineage-aware-path-resolver]
- [x] 0.3 Add `LineageId = NewType("LineageId", str)` in `lib/set_orch/types.py` (or equivalent); every public API in `LineagePaths` uses this type. Mypy run as part of CI catches callers that pass raw `str`. [REQ: centralized-lineage-aware-path-resolver]
- [x] 0.4 Add a filename-safe `slug(lineage_id: LineageId) -> str` helper; test edge cases (slashes, dots, unicode, very long paths, empty string). [REQ: spec-lineage-identity-derived-from-input-path]
- [x] 0.5 Mirror `LineagePaths` as Bash helpers in `bin/set-common.sh` — `lineage_plan_file`, `lineage_digest_dir`, `lineage_state_file`, etc. Every helper echoes the resolved path so shell scripts can consume it via `$(lineage_plan_file "$PROJECT" "$LINEAGE")`. [REQ: centralized-lineage-aware-path-resolver]
- [x] 0.6 Unit test: `tests/unit/test_lineage_paths.py` covers every property for (a) live lineage, (b) non-live lineage with rotated copy present, (c) non-live lineage with NO rotated copy → logs DEBUG + falls back, (d) `LineageId` typing catches raw str at mypy, (e) slug round-trips for tricky inputs. [REQ: centralized-lineage-aware-path-resolver]
- [x] 0.7 Unit test: `tests/unit/test_set_common_lineage_helpers.sh` exercises the Bash helpers against a fixture project. [REQ: centralized-lineage-aware-path-resolver]
- [x] 0.8 Migration helper — a deprecation shim for callers that still pass raw project_path without lineage_id: `LineagePaths.from_project(project_path)` auto-resolves the current live lineage from `state.spec_lineage_id`. Logs WARNING so callers who forgot to pass lineage become visible. [REQ: centralized-lineage-aware-path-resolver]
- [x] 0.9 Publish `LineagePaths` in the package public API (re-export from `set_orch/__init__.py` if other modules conventionally import from there). [REQ: centralized-lineage-aware-path-resolver]

## 1. Event stream rotation

- [x] 1.1 Add `_rotate_event_streams(state_file)` helper in `lib/set_orch/engine.py` that renames `orchestration-events.jsonl` and `orchestration-state-events.jsonl` to `*-cycle<N>.jsonl` (N = next unused integer) and creates fresh empty live files. Wrap in try/except OSError + WARNING log. [REQ: event-stream-rotation-on-replan-and-sentinel-stop]
- [x] 1.2 Call `_rotate_event_streams` as the first step inside `_auto_replan_cycle` (before `_archive_completed_to_jsonl`). [REQ: event-stream-rotation-on-replan-and-sentinel-stop]
- [x] 1.3 Call `_rotate_event_streams` from the sentinel clean-stop path (manager `/sentinel/stop` endpoint handler + `set-sentinel stop`) when `state.status != "done"`. [REQ: event-stream-rotation-on-replan-and-sentinel-stop]
- [x] 1.4 Unit test: rotation creates cycleN file, new empty live file, preserves content. [REQ: event-stream-rotation-on-replan-and-sentinel-stop]
- [x] 1.5 Unit test: rotation failure logs WARNING and replan continues. [REQ: event-stream-rotation-on-replan-and-sentinel-stop]

## 2. Archive session summaries

- [x] 2.1 Add `_compute_session_summary(worktree_path: str) -> dict` in `lib/set_orch/engine.py` that scans `~/.claude/projects/-<mangled>/*.jsonl` and returns the aggregate dict defined in spec. [REQ: archived-session-summaries]
- [x] 2.2 Extend `_archive_completed_to_jsonl` to set `entry["session_summary"] = _compute_session_summary(c.worktree_path)` when `worktree_path` is set; default to empty dict otherwise. [REQ: archived-session-summaries]
- [x] 2.3 Unit test: session summary aggregates call count + token totals + timestamps from a fixture session dir. [REQ: archived-session-summaries]
- [x] 2.4 Unit test: archive writer emits `session_summary` with expected keys. [REQ: archived-session-summaries]
- [x] 2.5 Unit test: missing session dir produces `session_summary` with zeros/nulls, no exception. [REQ: archived-session-summaries]

## 3. Backfill migration for legacy archives

- [x] 3.1 Add `migrate_legacy_archive(project_path)` helper in `lib/set_orch/migrations/backfill_lineage.py` that opens `state-archive.jsonl`, iterates entries, and for each entry missing `spec_lineage_id`: reads `orchestration-plan.json::input_path` → canonicalises → stamps the entry. Idempotent (skip entries already tagged). [REQ: backfill-migration-for-historic-archive-entries]
- [x] 3.2 Where the live-state snapshot at the time of archival can be recovered (e.g., from the state-events jsonl), also backfill `phase` onto entries that lack it. [REQ: backfill-migration-for-historic-archive-entries]
- [x] 3.3 Unrecoverable entries (no plan file, no snapshot hints) get `spec_lineage_id = "__unknown__"`, `phase = null`, and a WARNING log line. [REQ: backfill-migration-for-historic-archive-entries]
- [x] 3.4 Remove the existing `if "phase" not in entry: entry["phase"] = 0` fallback in `_load_archived_changes`. Reader returns entries as-is post-migration. [REQ: backfill-migration-for-historic-archive-entries]
- [x] 3.5 Wire migration into set-web service startup: runs once per project directory the first time the process touches its state. Gate behind a `.migrated-lineage` marker file to avoid repeated scans. [REQ: backfill-migration-for-historic-archive-entries]
- [x] 3.6 Unit test: legacy entry without `spec_lineage_id` + plan with `input_path = docs/spec.md` → entry is rewritten with `spec_lineage_id = "docs/spec.md"`. [REQ: backfill-migration-for-historic-archive-entries]
- [x] 3.7 Unit test: legacy entry without plan file → entry becomes `spec_lineage_id = "__unknown__"`, WARNING logged. [REQ: backfill-migration-for-historic-archive-entries]
- [x] 3.8 Unit test: re-running migration on an already-migrated file changes nothing (idempotency). [REQ: backfill-migration-for-historic-archive-entries]
- [x] 3.9 Unit test: modern entry with `spec_lineage_id` + `phase` is left untouched by migration. [REQ: backfill-migration-for-historic-archive-entries]

## 4. Rotated event concatenation

- [x] 4.1 Update `lib/set_orch/api/activity.py` event file collection loop to also glob `orchestration-events-cycle*.jsonl` and `orchestration-state-events-cycle*.jsonl` in cycle order, read each into the events list before reading the live files. [REQ: rotated-event-concatenation-for-readers]
- [x] 4.2 Update `_read_llm_call_events` in `lib/set_orch/api/orchestration.py` to include rotated cycle files alongside the live file, deduplicating by `(ts, change, purpose)`. [REQ: rotated-event-concatenation-for-readers]
- [x] 4.3 Integration test: multi-cycle fixture project → activity timeline returns spans from cycle 1 + live file, ordered chronologically. [REQ: rotated-event-concatenation-for-readers]
- [x] 4.4 Integration test: llm-calls endpoint returns events from both cycle files interleaved by timestamp. [REQ: rotated-event-concatenation-for-readers]

## 4b. Per-lineage plan and digest retention

- [x] 4b.1 Add `_rotate_plan_and_digest_for_new_lineage(project_path, new_lineage_id)` helper in `lib/set_orch/engine.py` that, when called at sentinel-start and the current on-disk `orchestration-plan.json` belongs to a different lineage, renames: `orchestration-plan.json` → `orchestration-plan-<old-slug>.json`, `orchestration-plan-domains.json` → `orchestration-plan-domains-<old-slug>.json`, `set/orchestration/digest/` → `set/orchestration/digest-<old-slug>/`. Slug is a filename-safe form of the lineage id. [REQ: per-lineage-plan-and-digest-retention]
- [x] 4b.2 Call `_rotate_plan_and_digest_for_new_lineage` from the sentinel-start path BEFORE the new lineage's plan is written or its digest is decomposed. [REQ: per-lineage-plan-and-digest-retention]
- [x] 4b.3 Update the planner's digest-dir resolution (`planner.py` + `engine.py` sites that do `os.path.join(os.getcwd(), "set", "orchestration", "digest")`) to consult the lineage: if the caller is operating under a non-live lineage, use `set/orchestration/digest-<slug>/` instead of the live dir. [REQ: per-lineage-plan-and-digest-retention]
- [x] 4b.4 Update `/api/<project>/digest` (and related endpoints: `requirements`, `coverage-report`) to read the lineage-specific plan and digest files when `?lineage=<id>` is not the live lineage. Return an explicit "plan unavailable for lineage" response if neither `orchestration-plan-<slug>.json` nor the live file matches. [REQ: per-lineage-plan-and-digest-retention]
- [x] 4b.5 Migration path for existing projects: if a project has a live plan but no rotated copies yet, the first sentinel start under a different spec triggers the rename — no retroactive work needed. [REQ: per-lineage-plan-and-digest-retention]
- [x] 4b.6 Unit test: switching from v1 to v2 at sentinel start renames v1 plan/digest with slug; live files are fresh for v2. [REQ: per-lineage-plan-and-digest-retention]
- [x] 4b.7 Unit test: reading digest under `?lineage=v1` after v2 takeover returns v1's data (from the renamed dir), not v2's live digest. [REQ: per-lineage-plan-and-digest-retention]
- [x] 4b.8 Unit test: if a lineage has no saved plan (never been decomposed), API returns an explicit unavailable response rather than falling back to another lineage's data. [REQ: per-lineage-plan-and-digest-retention]

## 4c. Supervisor status lineage awareness

- [x] 4c.1 Add `spec_lineage_id` to `.set/supervisor/status.json` (already has a `spec` field — keep for compatibility but add the normalised lineage id too). Written on sentinel start. [REQ: spec-lineage-identity-derived-from-input-path]
- [x] 4c.2 When the sentinel stops cleanly (SIGTERM, stop endpoint), archive the supervisor status snapshot alongside the rotated event files so each session's status metadata is retained: append a JSON line to `.set/supervisor/status-history.jsonl` with the full status + the `rotated_at` timestamp. [REQ: sentinel-session-id-as-sub-dimension]
- [x] 4c.3 Unit test: status.json gets spec_lineage_id on sentinel start; status-history.jsonl gains a line on clean stop. [REQ: sentinel-session-id-as-sub-dimension]

## 5. Worktree history tracking

- [x] 5.1 Add `_append_worktree_history(project_path, change_name, original_path, removed_path)` helper in `lib/set_orch/merger.py` that writes the JSON line defined in spec. [REQ: retained-worktree-history]
- [x] 5.2 Call the helper from `cleanup_worktree` right after the rename-to-`.removed.<epoch>` succeeds. [REQ: retained-worktree-history]
- [x] 5.3 Add `--purge` flag to `bin/set-close` that deletes the `.removed.*` dir AND updates its history entry to `purged = true`. [REQ: retained-worktree-history]
- [x] 5.4 Default `set-close` (no `--purge`) stops at rename — no physical deletion. [REQ: retained-worktree-history]
- [x] 5.5 Unit test: cleanup appends the expected JSON line with `purged = false`. [REQ: retained-worktree-history]
- [x] 5.6 Unit test: `set-close --purge` deletes the `.removed.*` dir and flips the history line's `purged` flag. [REQ: retained-worktree-history]

## 6. Phase offset on replan and new session (lineage-scoped)

- [x] 6.1 Add `compute_phase_offset(state_file, lineage_id) -> int` helper in `lib/set_orch/planner.py` that returns `max(live+archived phases tagged with lineage_id) - 1` (minimum 0). Offset computation reads ONLY records matching `lineage_id`. [REQ: phase-offset-within-a-lineage]
- [x] 6.2 Apply the offset in the replan pipeline's plan-write step using the current `state.spec_lineage_id`: shift every new change's `phase` by `compute_phase_offset(state_file, state.spec_lineage_id) - min_new_phase + 1`. Clamp to never produce phase < 1. [REQ: phase-offset-within-a-lineage]
- [x] 6.3 Apply the same offset in the initial plan-write path that runs on sentinel start, using the lineage the new sentinel was started with. [REQ: phase-offset-within-a-lineage]
- [x] 6.4 When the sentinel starts on a lineage that has NO matching archive/state records, `compute_phase_offset` returns 0 and the planner's native numbering is preserved. [REQ: fresh-phase-numbering-for-a-new-lineage]
- [x] 6.5 Unit test: v1 lineage with archived phases 0,1,2 + replan output phases 1,2 → shifted to 3,4 under v1. [REQ: phase-offset-within-a-lineage]
- [x] 6.6 Unit test: v1 lineage has archived phases 0,1,2; fresh sentinel start on v2 with plan phases 1,2 → no offset applied, v2 phases remain 1,2. [REQ: fresh-phase-numbering-for-a-new-lineage]
- [x] 6.7 Unit test: sentinel restart on v1 (same lineage) picks up from `max(v1 archived) + 1`. [REQ: phase-offset-within-a-lineage]
- [x] 6.8 Unit test: brand-new project (empty archive + empty state) applies offset 0. [REQ: fresh-phase-numbering-for-a-new-lineage]

## 7. Spec lineage + sentinel session state

- [x] 7.1 Add `spec_lineage_id: Optional[str]`, `sentinel_session_id: Optional[str]`, `sentinel_session_started_at: Optional[str]` fields to `OrchestratorState` and `Change` in `lib/set_orch/state.py`. [REQ: spec-lineage-identity-derived-from-input-path]
- [x] 7.2 At sentinel start, read `--spec` argument → normalise to a project-relative POSIX path → store as `state.spec_lineage_id`. Also generate fresh `sentinel_session_id = uuid.uuid4().hex` and `sentinel_session_started_at = <iso>`. [REQ: spec-lineage-identity-derived-from-input-path]
- [x] 7.3 Propagate both `spec_lineage_id` and `sentinel_session_id` onto every Change created (init, replan) and every archive entry. [REQ: spec-lineage-identity-derived-from-input-path]
- [x] 7.4 Do NOT regenerate `sentinel_session_id` on replan — preserved for the entire sentinel session. `spec_lineage_id` is always propagated unchanged mid-session. [REQ: sentinel-session-id-as-sub-dimension]
- [x] 7.5 Unit test: sentinel start with `--spec docs/spec-v1.md` → `state.spec_lineage_id = "docs/spec-v1.md"`. [REQ: spec-lineage-identity-derived-from-input-path]
- [x] 7.6 Unit test: path canonicalisation — absolute and relative paths referring to same file resolve to the same `spec_lineage_id`. [REQ: spec-lineage-identity-derived-from-input-path]
- [x] 7.7 Unit test: session_id survives replan; lineage survives replan and restart-same-spec. [REQ: sentinel-session-id-as-sub-dimension]
- [x] 7.8 Unit test: session_id is fresh after stop+start; lineage stays the same if the same spec is used again. [REQ: sentinel-session-id-as-sub-dimension]

## 8. Activity timeline session markers

- [x] 8.1 In `lib/set_orch/api/activity.py`, after event concatenation, scan events for `sentinel_session_id` changes and emit a zero-width `sentinel:session_boundary` span at each boundary with `detail.session_id` + `detail.session_started_at`. [REQ: sentinel-session-boundary-markers-in-the-timeline]
- [x] 8.2 Integration test: multi-session fixture → activity timeline contains exactly `(N_sessions - 1)` boundary spans, placed at the right timestamps. [REQ: sentinel-session-boundary-markers-in-the-timeline]
- [ ] 8.3 UI: `web/src/components/ActivityTimeline.tsx` renders `sentinel:session_boundary` spans as full-height dividers with a "Session <short-id>" label. [REQ: sentinel-session-boundary-markers-in-the-timeline]

## 9. Plan-version propagation verification

- [x] 9.1 Confirm `plan_version` is already written by `_archive_completed_to_jsonl` (landed in the archive fix); extend its test to also confirm plan_version propagates through to the API response. [REQ: plan-version-propagation-on-archive]
- [ ] 9.2 UI: `web/src/components/PhaseView.tsx` groups archive+live entries by `(phase, plan_version)` when two distinct plan versions share a phase number; single-version phases render as before. [REQ: plan-version-propagation-on-archive]
- [ ] 9.3 Integration test: Phases tab renders "Phase 1 (plan v1)" and "Phase 1 (plan v2)" as separate subheaders when archive has v1 phase-1 entries and live state has v2 phase-1 entries. [REQ: plan-version-propagation-on-archive]

## 10. Token panel archive awareness

- [x] 10.1 Update token-total aggregation in `lib/set_orch/api/helpers.py::_enrich_changes` (or the equivalent StatusHeader path) to include archive-sourced token fields. [REQ: token-aggregation-includes-archived-changes]
- [x] 10.2 In `_read_session_calls`, emit one synthetic `source = "archive_summary"` call per archived change whose worktree session dir is absent but which has `session_summary` data. [REQ: token-aggregation-includes-archived-changes]
- [ ] 10.3 UI: `web/src/components/TokensPanel.tsx` renders `_archived` rows with the "(archived)" label, sorted after live rows, token values sourced from archive entry fields. [REQ: token-panel-renders-archived-rows-explicitly]
- [x] 10.4 Integration test: Tokens panel shows all archived + live changes with correct token values after worktree cleanup simulation. [REQ: token-aggregation-includes-archived-changes]

## 11. Coverage history append

- [x] 11.1 Add `_append_coverage_history(project_path, change_name, plan_version, session_id, reqs)` helper in `lib/set_orch/merger.py` that writes the JSON line defined in spec. [REQ: coverage-history-append-on-every-merge]
- [x] 11.2 Call the helper from the post-merge coverage regeneration step in `merger.py` (success path only). [REQ: coverage-history-append-on-every-merge]
- [x] 11.3 Update Digest/Reqs API endpoint to consult `spec-coverage-history.jsonl` for REQs not covered by the live plan, returning `merged_by`, `merged_by_archived = true`, `merged_at`. [REQ: digest-attribution-uses-history]
- [ ] 11.4 UI: `web/src/components/DigestPanel.tsx` attribution column renders "merged by foundation-setup (archived, YYYY-MM-DD)" for archived-sourced REQ status. [REQ: digest-attribution-uses-history]
- [x] 11.5 Unit test: coverage history line has the expected shape and is appended per merge. [REQ: coverage-history-append-on-every-merge]
- [x] 11.6 Unit test: Digest/Reqs API returns the archived attribution for a REQ that only exists in history. [REQ: digest-attribution-uses-history]

## 12. E2E manifest history append

- [x] 12.1 Add `_append_e2e_manifest_history(project_path, change_name, plan_version, session_id, manifest)` helper in `lib/set_orch/merger.py`. [REQ: e2e-manifest-history-append-on-merge]
- [x] 12.2 Call the helper from the post-merge artifact collection path; skip silently when the worktree has no `e2e-manifest.json`. [REQ: e2e-manifest-history-append-on-merge]
- [x] 12.3 Update Digest/E2E API endpoint to aggregate `e2e-manifest-history.jsonl` lines with the current per-change manifests. [REQ: digest-e2e-aggregates-across-cycles]
- [ ] 12.4 UI: `web/src/components/DigestPanel.tsx` E2E subtab renders one block per change (live or archived), with `archived = true` blocks styled distinctly; header shows the combined test count. [REQ: digest-e2e-aggregates-across-cycles]
- [x] 12.5 Unit test: merge appends the manifest line with correct metadata. [REQ: e2e-manifest-history-append-on-merge]
- [x] 12.6 Integration test: Digest/E2E returns live + history blocks combined and correctly totalled. [REQ: digest-e2e-aggregates-across-cycles]

## 13. Lineage filter plumbing across APIs

- [x] 13.1 Add `spec_lineage_id` to the `CYCLE_HEADER` event written at the top of each rotated event file in `lib/set_orch/engine.py::_rotate_event_streams`. [REQ: lineage-tagging-on-all-history-records]
- [x] 13.2 Add `spec_lineage_id` to every archive entry in `_archive_completed_to_jsonl`, every coverage/e2e/worktree history line in the respective appenders. [REQ: lineage-tagging-on-all-history-records]
- [x] 13.3 Add `/api/<project>/lineages` endpoint returning the lineage list with metadata (display_name, first/last_seen_at, is_live, change_count, merged_count). `is_live = true` only when the lineage matches `state.spec_lineage_id` AND the sentinel is running. [REQ: lineages-listing-endpoint]
- [x] 13.4 Accept `?lineage=<id>` (with special value `__all__`) on `/api/<project>/state`, `/api/<project>/activity-timeline`, `/api/<project>/llm-calls`, `/api/<project>/digest`, `/api/<project>/digest/e2e`. Default when omitted is `state.spec_lineage_id` when sentinel running, else the lineage with `max(last_seen_at)`. [REQ: data-endpoints-accept-an-optional-lineage-filter]
- [x] 13.5 `__unknown__` lineage is returned by `/api/<project>/lineages` only when unrecoverable entries exist post-migration, and is annotated with `diagnostic` note. [REQ: lineages-listing-endpoint]
- [x] 13.6 Implement coverage denominator scoping in `/api/<project>/digest` — read the lineage's own input spec file to derive the REQ set, use that as denominator, ignore REQs outside the lineage's spec. [REQ: coverage-denominator-is-the-lineages-own-spec]
- [x] 13.7 Unit test matrix: each filtered endpoint returns only matching records; `__all__` returns union; omitted defaults to live-or-latest lineage per rule. [REQ: data-endpoints-accept-an-optional-lineage-filter]
- [x] 13.8 Unit test: v2 lineage with 3-REQ spec + 1 v2-merged change covering all 3 → coverage reports 3/3 = 100%, v1's 120 REQs do NOT appear in v2 response. [REQ: coverage-denominator-is-the-lineages-own-spec]
- [x] 13.9 Unit test: REQ-X in v1 spec, not in v2 spec → GET /digest?lineage=v2 does NOT include REQ-X at all (not as uncovered either). [REQ: coverage-denominator-is-the-lineages-own-spec]

## 14. UI: Left-sidebar lineage list

- [ ] 14.1 Identify the existing sidebar component (`web/src/components/Sidebar.tsx` or the project menu under the `SET / Ship Exactly This!` header that currently renders `Orchestration / Issues / Memory / Settings`). Add a new `LineageList` section rendered BETWEEN the project-name block and the existing menu items. [REQ: left-sidebar-lineage-list]
- [ ] 14.2 `LineageList` fetches `/api/<project>/lineages` on mount and when the sentinel's state changes. Renders the "All lineages" entry at the top, then one row per lineage with `display_name` and a green dot when `is_live = true`. [REQ: left-sidebar-lineage-list]
- [ ] 14.3 Clicking a lineage row sets the selection and triggers a refetch across every tab through the lineage context. [REQ: left-sidebar-lineage-list]
- [ ] 14.4 Introduce a `SelectedLineageProvider` (React context) so every tab component reads the current selection and appends `?lineage=...` to its data fetches. [REQ: data-endpoints-accept-an-optional-lineage-filter]
- [ ] 14.5 Update `Dashboard.tsx` data fetchers (state polling, changes list, activity timeline, tokens call list, digest, e2e) to include the lineage query parameter from context. [REQ: data-endpoints-accept-an-optional-lineage-filter]
- [ ] 14.6 Persist selection in `localStorage` under `set-lineage-<project>`; restore on mount; fall back to default-selection rule when stored id is unknown. [REQ: left-sidebar-lineage-list]
- [ ] 14.7 Default selection on first load: `is_live = true` lineage if present, else the one with the newest `last_seen_at`. [REQ: left-sidebar-lineage-list]
- [ ] 14.8 `StatusHeader` status badge stays bound to the **live** lineage (`state.spec_lineage_id`). When selection differs from live, render a text hint "Viewing <display_name> — sentinel running <live display_name>" adjacent to the badge. [REQ: left-sidebar-lineage-list]
- [ ] 14.9 "All lineages" (`__all__`) mode: tables/lists include a `Lineage` column; Phases tab shows a top-level section per lineage; selected state in the sidebar highlights the "All lineages" row. [REQ: left-sidebar-lineage-list]
- [ ] 14.10 Playwright test: two-lineage fixture → sidebar lists both; clicking v1 while v2 runs filters every tab to v1 AND sentinel continues running v2 AND StatusHeader badge stays on v2. [REQ: left-sidebar-lineage-list]
- [ ] 14.11 Playwright test: selection survives page reload. [REQ: left-sidebar-lineage-list]
- [ ] 14.12 Playwright test: "All lineages" mode shows the Lineage column/section on every relevant tab. [REQ: left-sidebar-lineage-list]

## 15. PhaseView per-lineage cleanup

- [ ] 15.1 `web/src/components/PhaseView.tsx` no longer renders a synthetic "Phase 0" header for untagged legacy entries — post-migration they either carry a real phase or belong to `__unknown__` (which is gated behind an explicit "show unattributed" affordance, not default-visible). [REQ: backfill-migration-for-historic-archive-entries]
- [ ] 15.2 Phase numbers are scoped to the currently selected lineage; switching lineage rebuilds the phase groups from the filtered change list. [REQ: left-sidebar-lineage-list]
- [ ] 15.3 Playwright test: v1-fixture project renders Phase 1, Phase 2, Phase 3 (v1 spec's phases); switching to v2 renders v2's own phases (fresh numbering). [REQ: left-sidebar-lineage-list]
- [ ] 15.4 Playwright test: a modern post-migration project does NOT render any "Previous cycles" / "Phase 0 (archived)" synthetic header — regression guard. [REQ: backfill-migration-for-historic-archive-entries]

## 15b. Per-file migration sweep (driven by migration-audit.md)

These tasks mirror `migration-audit.md`'s checklist 1:1. Each task below translates a row from the audit into a concrete "replace hardcoded literals with `LineagePaths` calls" commit. Progress tracking on both artefacts stays in sync (check the box here AND in `migration-audit.md`).

### 15b.a — Python core (highest impact first)

- [ ] 15b.1 `lib/set_orch/engine.py` — replace all state/plan/archive/coverage literals with `LineagePaths` calls. [REQ: centralized-lineage-aware-path-resolver]
- [x] 15b.2 `lib/set_orch/_api_old.py` — 17 refs. Decide migrate-or-deprecate; if deprecate, add a blocking test so new code stops importing from it. [REQ: centralized-lineage-aware-path-resolver]
- [ ] 15b.3 `lib/set_orch/supervisor/daemon.py` — events + state reads via resolver. [REQ: centralized-lineage-aware-path-resolver]
- [ ] 15b.4 `lib/set_orch/merger.py` — manifest, config, state reads. [REQ: centralized-lineage-aware-path-resolver]
- [ ] 15b.5 `lib/set_orch/api/orchestration.py` — drop dual-location fallback; resolver owns it. [REQ: centralized-lineage-aware-path-resolver]
- [ ] 15b.6 `lib/set_orch/dispatcher.py` — manifest WRITE via resolver. [REQ: centralized-lineage-aware-path-resolver]
- [x] 15b.7 `lib/set_orch/planner.py` — plan + domains WRITE, digest READ. [REQ: centralized-lineage-aware-path-resolver]
- [x] 15b.8 `lib/set_orch/cli.py` — CLI defaults reference the resolver (compute default at parse time from cwd + current lineage). [REQ: centralized-lineage-aware-path-resolver]
- [ ] 15b.9 Remaining Python modules in `migration-audit.md` Phase 2 (verifier, recovery, config, digest, events, reporter, auditor, notifications, cross_change, loop_prompt, loop_state, api/helpers, api/activity, api/activity_detail, api/sessions, api/actions, api/sentinel, api/lifecycle, api/media, api/_sentinel_orch, issues/registry, issues/watchdog, issues/manager, manager/service, profile_loader, profile_types, subprocess_utils, state, sentinel/findings, sentinel/orchestrator). One sub-task per file; commit per file or per small cluster. [REQ: centralized-lineage-aware-path-resolver]

### 15b.b — Bash migration

- [ ] 15b.10 `bin/set-orchestrate` — dynamic path derivation goes through `set-common.sh` helpers. [REQ: centralized-lineage-aware-path-resolver]
- [ ] 15b.11 `bin/set-sentinel`, `bin/set-status`, `bin/set-web`, `bin/set-manager`, `bin/set-close`, `bin/set-new`, `bin/set-merge`, `bin/set-harvest`, `bin/set-project` — each reviewed; any orchestration-path literal replaced with a helper call. [REQ: centralized-lineage-aware-path-resolver]
- [ ] 15b.12 `lib/orchestration/*.sh` + `lib/loop/*.sh` — confirm still in use; if obsoleted by Python cutover, delete the file and mark `[/]` in the audit. Otherwise migrate. [REQ: centralized-lineage-aware-path-resolver]
- [ ] 15b.13 `scripts/*.sh` — migrate remaining sidecar scripts. [REQ: centralized-lineage-aware-path-resolver]

### 15b.c — Tests

- [ ] 15b.14 `tests/orchestrator/test-orchestrate-integration.sh` — 84 refs. Introduce test helpers that mirror `LineagePaths`; use the helpers for every path construction. [REQ: centralized-lineage-aware-path-resolver]
- [ ] 15b.15 `tests/unit/*.py` + `tests/unit/*.sh` — replace hardcoded literals with resolver calls. [REQ: centralized-lineage-aware-path-resolver]

### 15b.d — Web frontend lineage plumbing audit

- [ ] 15b.16 Confirm every `fetch(` in `web/src/**` that hits an orchestration endpoint appends the current `selectedLineage` query parameter via the shared helper. No raw string-literal path fetches outside that helper. Playwright test asserts the Network tab shows `?lineage=<id>` on every relevant request. [REQ: data-endpoints-accept-an-optional-lineage-filter]

## 17. Hardcoded-path audit gate

- [x] 17.1 New script `scripts/audit-lineage-paths.sh` runs ripgrep for each of the 18 canonical patterns across `lib/`, `bin/`, `scripts/`, `web/src/`, `tests/`. Exits 0 if every residual match is inside `lib/set_orch/paths.py`, `bin/set-common.sh`, or tests/fixtures that exercise the resolver. Exits non-zero with a per-file listing otherwise. [REQ: hardcoded-path-audit-gate-blocks-archiving]
- [ ] 17.2 Wire the script into the verify pipeline for this change: `/opsx:verify run-history-and-phase-continuity` invokes it. Non-zero exit blocks `/opsx:archive`. [REQ: hardcoded-path-audit-gate-blocks-archiving]
- [x] 17.3 The script writes its diff-style output to `openspec/changes/run-history-and-phase-continuity/audit-report.txt` every time it runs, so reviewers can see exactly which residuals remain. [REQ: hardcoded-path-audit-gate-blocks-archiving]
- [x] 17.4 Update `migration-audit.md` checkboxes automatically from the script output (inverse: auto-check rows whose file no longer appears in the residuals list). Store a `--sync-audit` flag. [REQ: hardcoded-path-audit-gate-blocks-archiving]
- [x] 17.5 Unit test: fixture project with a known hardcoded literal → script exits non-zero and names the file. [REQ: hardcoded-path-audit-gate-blocks-archiving]
- [x] 17.6 Unit test: fixture project with only resolver-routed references → script exits 0. [REQ: hardcoded-path-audit-gate-blocks-archiving]
- [ ] 17.7 Add a `pre-commit` / pre-push invocation of the script (optional but recommended) so the diff cannot regress silently. [REQ: hardcoded-path-audit-gate-blocks-archiving]

## 16. Final integration + regression

- [x] 16.1 Run the full unit suite (`pytest tests/unit -q`) — confirm 0 regressions. [REQ: event-stream-rotation-on-replan-and-sentinel-stop]
- [ ] 16.2 Run the web E2E suite against a fixture with multi-lineage history, confirm Activity/Tokens/Digest/E2E tabs all render lineage-filtered content. [REQ: data-endpoints-accept-an-optional-lineage-filter]
- [ ] 16.3 Smoke-test the craftbrew-run-20260418-1719 project: backfill migration attributes its archive entries to `docs/` (its plan's input_path), sidebar shows that lineage, phases 1+2 continue to display under it. No `__legacy__` / `__unknown__` entries expected for a project whose plan file exists. [REQ: backfill-migration-for-historic-archive-entries]
- [ ] 16.4 End-to-end scenario: start sentinel on `docs/spec-v1.md`, let it archive a phase, stop it. Start sentinel on `docs/spec-v2.md`. Verify: sidebar shows both lineages, v2 is live default, clicking v1 shows v1's archived content without disturbing v2's execution. [REQ: left-sidebar-lineage-list]
- [x] 16.5 Document the new files (`orchestration-events-cycle*.jsonl`, `spec-coverage-history.jsonl`, `e2e-manifest-history.jsonl`, `worktrees-history.json`) + lineage selector usage in `docs/` (run-layout reference if present, otherwise note in PR description). [REQ: retained-worktree-history]

## Acceptance Criteria (from spec scenarios)

### Event stream rotation
- [x] AC-1: WHEN monitor loop triggers `_auto_replan_cycle` for cycle N THEN `orchestration-events.jsonl` is rotated to `orchestration-events-cycle<N>.jsonl` before the new plan is written [REQ: event-stream-rotation-on-replan-and-sentinel-stop, scenario: replan-preserves-previous-cycle-events]
- [x] AC-2: WHEN sentinel is stopped while orchestration is not done THEN the live events file is rotated to a new cycle file and a fresh empty live file is created [REQ: event-stream-rotation-on-replan-and-sentinel-stop, scenario: sentinel-clean-stop-rotates-the-live-stream]
- [x] AC-3: WHEN rotation fails with OSError THEN the failure is logged at WARNING and replan continues [REQ: event-stream-rotation-on-replan-and-sentinel-stop, scenario: rotation-failure-does-not-block-replan]

### Session summaries
- [x] AC-4: WHEN archive writer writes a change with worktree_path THEN the entry includes session_summary with call_count, token fields, first/last ts, total_duration_ms [REQ: archived-session-summaries, scenario: session-summary-fields]
- [x] AC-5: WHEN archive reader loads an entry without session_summary THEN the entry is returned as-is without synthesized zeros [REQ: archived-session-summaries, scenario: legacy-archive-entries]

### Archive source marker
- [x] AC-6: WHEN a legacy entry has no spec_lineage_id AND the project's plan file has input_path=docs/spec.md THEN migration rewrites the entry with spec_lineage_id=docs/spec.md [REQ: backfill-migration-for-historic-archive-entries, scenario: migration-attributes-legacy-entries]
- [x] AC-7: WHEN an entry cannot be attributed (no plan file, no snapshots) THEN it becomes spec_lineage_id="__unknown__", phase=null, WARNING logged [REQ: backfill-migration-for-historic-archive-entries, scenario: migration-cannot-recover-attribution]
- [x] AC-7a: WHEN migration runs on an already-migrated archive THEN no entries are modified (idempotency) [REQ: backfill-migration-for-historic-archive-entries, scenario: current-writer-entries-untouched]

### Rotated event concatenation
- [x] AC-8: WHEN activity timeline API is invoked AND cycle files exist THEN it reads all cycleN files in ascending order then the live file, ordered by event timestamp [REQ: rotated-event-concatenation-for-readers, scenario: activity-timeline-reads-all-cycles]
- [x] AC-9: WHEN /api/<project>/llm-calls is called AND cycle files exist THEN calls from all cycles are interleaved by timestamp [REQ: rotated-event-concatenation-for-readers, scenario: llm-calls-api-includes-rotated-events]

### Worktree history
- [x] AC-10: WHEN cleanup_worktree renames a worktree to .removed.<epoch> THEN a JSON line is appended to worktrees-history.json with purged=false [REQ: retained-worktree-history, scenario: cleanup-writes-history]
- [x] AC-11: WHEN set-close --purge runs THEN the .removed dir is deleted AND the history entry's purged field becomes true [REQ: retained-worktree-history, scenario: purge-is-explicit]
- [x] AC-12: WHEN set-close runs without --purge THEN the .removed dir remains on disk [REQ: retained-worktree-history, scenario: purge-is-explicit]

### Spec lineage identity
- [x] AC-13a: WHEN sentinel starts with `--spec docs/spec-v1.md` THEN state.spec_lineage_id = "docs/spec-v1.md" and every new Change + archive entry carries that id [REQ: spec-lineage-identity-derived-from-input-path, scenario: sentinel-started-with-spec-v1-md]
- [x] AC-13b: WHEN sentinel is restarted with `--spec docs/spec-v2.md` THEN new state.spec_lineage_id = v2 AND previous v1 archive entries remain tagged v1 [REQ: spec-lineage-identity-derived-from-input-path, scenario: operator-switches-to-spec-v2-md]
- [x] AC-13c: WHEN an absolute and a relative path refer to the same file THEN both resolve to the same canonical spec_lineage_id [REQ: spec-lineage-identity-derived-from-input-path, scenario: path-canonicalisation]

### Phase offset (lineage-scoped)
- [x] AC-14a: WHEN v1 lineage archive has phases 0,1,2 AND replan output has phases 1,2 THEN they shift to 3,4 under v1 [REQ: phase-offset-within-a-lineage, scenario: replan-continues-a-lineage]
- [x] AC-14b: WHEN v1 lineage is stopped and restarted on the same spec with plan phases 1,2 THEN they shift to 3,4 [REQ: phase-offset-within-a-lineage, scenario: restart-same-spec-continues-numbering]
- [x] AC-14c: WHEN v1 has archived phases 0,1,2 AND a new sentinel starts with `--spec v2.md` using plan phases 1,2 THEN offset is 0 and phases stay 1,2 [REQ: phase-offset-within-a-lineage, scenario: other-lineages-phases-are-ignored]
- [x] AC-14d: WHEN archive has only v1 AND sentinel starts with v2.md THEN v2 numbering is used verbatim (no offset) [REQ: fresh-phase-numbering-for-a-new-lineage, scenario: first-ever-session-on-a-new-spec]

### Sentinel session metadata (sub-dimension)
- [x] AC-17a: WHEN sentinel is stopped and restarted on the same lineage THEN both sessions share spec_lineage_id AND each carries its own sentinel_session_id AND lineage UI groups them together [REQ: sentinel-session-id-as-sub-dimension, scenario: multiple-restarts-on-the-same-lineage]
- [x] AC-18: WHEN replan fires mid-session THEN sentinel_session_id is preserved on all newly generated changes (not regenerated) [REQ: sentinel-session-id-as-sub-dimension, scenario: session-id-survives-replan]

### Session boundary markers
- [x] AC-19: WHEN events span two sessions THEN a zero-width sentinel:session_boundary span with detail.session_id and detail.session_started_at is emitted at the boundary [REQ: sentinel-session-boundary-markers-in-the-timeline, scenario: two-sentinel-sessions-in-the-run]

### Plan-version propagation
- [ ] AC-20: WHEN two plan versions share the same phase number THEN UI renders separate subheaders "Phase N (plan v<X>)" and "Phase N (plan v<X+1>)" [REQ: plan-version-propagation-on-archive, scenario: same-phase-collision]

### Token aggregation
- [x] AC-21: WHEN state-archive.jsonl has input/output/cache tokens AND worktree was cleaned up THEN top-level token totals include them AND the Tokens panel row shows the values (not dashes) [REQ: token-aggregation-includes-archived-changes, scenario: archived-change-totals]
- [x] AC-22: WHEN archive entry has session_summary but worktree session dir is absent THEN /api/<project>/llm-calls emits a synthetic aggregate call with source=archive_summary [REQ: token-aggregation-includes-archived-changes, scenario: session-summary-fallback-for-llm-calls]
- [ ] AC-23: WHEN Tokens panel receives changes with _archived=true THEN archived rows show "(archived)" label, token values come from archive entry, archived rows sort after live rows [REQ: token-panel-renders-archived-rows-explicitly, scenario: archived-row-rendering]

### Coverage history
- [x] AC-24: WHEN a change merges and covers REQs THEN a JSON line is appended to spec-coverage-history.jsonl with change, plan_version, session_id, merged_at, reqs [REQ: coverage-history-append-on-every-merge, scenario: merge-regenerates-coverage]
- [x] AC-25: WHEN replan drops REQs from current plan THEN spec-coverage-history.jsonl entries remain intact and reads still resolve to "merged by foundation-setup (archived)" [REQ: coverage-history-append-on-every-merge, scenario: replan-does-not-wipe-history]
- [x] AC-26: WHEN Digest requests a REQ not under any current-plan change AND history has an archived attribution THEN response includes merged_by, merged_by_archived=true, merged_at [REQ: digest-attribution-uses-history, scenario: req-covered-by-archived-change]
- [x] AC-27: WHEN a REQ is neither in live plan nor history THEN it is marked uncovered [REQ: digest-attribution-uses-history, scenario: req-not-in-history-at-all]

### Per-lineage plan/digest retention
- [x] AC-27a: WHEN sentinel starts with --spec v2.md AND current live plan/digest belong to v1 THEN v1 files are renamed with `-<v1-slug>` suffix before v2 gets fresh empty files [REQ: per-lineage-plan-and-digest-retention, scenario: sentinel-opens-a-second-lineage]
- [x] AC-27b: WHEN a consumer reads digest under lineage v1 AND v2 is live THEN the reader uses `digest-<v1-slug>/` not the live `digest/` [REQ: per-lineage-plan-and-digest-retention, scenario: digest-read-honours-lineage]
- [x] AC-27c: WHEN a lineage has no saved plan file THEN API returns an explicit unavailable response, not another lineage's data [REQ: per-lineage-plan-and-digest-retention, scenario: plan-read-honours-lineage]

### E2E manifest history
- [x] AC-28: WHEN change merges with passing e2e-manifest.json THEN a line is appended to e2e-manifest-history.jsonl with the full manifest object and metadata [REQ: e2e-manifest-history-append-on-merge, scenario: merge-with-passing-e2e-manifest]
- [x] AC-29: WHEN change merges without an e2e-manifest.json THEN no line is appended and absence is logged at DEBUG (not WARNING) [REQ: e2e-manifest-history-append-on-merge, scenario: merge-with-missing-manifest]
- [x] AC-30: WHEN live plan + history contain 4 distinct changes' manifests THEN Digest/E2E returns all 4 blocks totalled with archived=true flag on historic ones [REQ: digest-e2e-aggregates-across-cycles, scenario: archived-live-blocks]
- [x] AC-31: WHEN e2e-manifest-history.jsonl does not exist THEN the API falls back to current live-manifest behaviour without raising [REQ: digest-e2e-aggregates-across-cycles, scenario: legacy-archive-without-history]

### Centralized path resolver
- [x] AC-32a: WHEN a caller asks LineagePaths(project, lineage="v1") for plan_file AND a rotated orchestration-plan-<v1-slug>.json exists THEN the resolver returns that rotated path [REQ: centralized-lineage-aware-path-resolver, scenario: resolver-returns-lineage-specific-path]
- [x] AC-32b: WHEN the caller asks for a path under the live lineage THEN the resolver returns the live orchestration-plan.json (not the slugged copy) [REQ: centralized-lineage-aware-path-resolver, scenario: resolver-returns-live-path-for-live-lineage]
- [x] AC-32c: WHEN any Bash script needs an orchestration path THEN it calls a helper in bin/set-common.sh that mirrors the Python resolver; no hardcoded literals elsewhere [REQ: centralized-lineage-aware-path-resolver, scenario: bash-helper-mirrors-python-resolver]

### Hardcoded-path audit gate
- [x] AC-32d: WHEN the audit gate greps code files AND a production file still contains a hardcoded orchestration-path literal outside the resolver THEN the gate FAILS with the file+line in its message AND /opsx:archive is blocked [REQ: hardcoded-path-audit-gate-blocks-archiving, scenario: audit-finds-a-residual-literal]
- [x] AC-32e: WHEN every code file's literal orchestration-path refs have been replaced by LineagePaths calls (or marked [~] / [/]) THEN the gate PASSES AND /opsx:archive may proceed [REQ: hardcoded-path-audit-gate-blocks-archiving, scenario: audit-passes]
- [x] AC-32f: WHEN the audit runs THEN it does NOT inspect markdown documentation, YAML templates, or openspec artefacts [REQ: hardcoded-path-audit-gate-blocks-archiving, scenario: non-code-files-excluded]

### Lineage tagging on history records
- [x] AC-32: WHEN _archive_completed_to_jsonl writes an entry THEN the entry includes spec_lineage_id sourced from state.spec_lineage_id [REQ: lineage-tagging-on-all-history-records, scenario: archive-entry]
- [x] AC-33: WHEN _rotate_event_streams creates orchestration-events-cycleN.jsonl THEN the first line is a CYCLE_HEADER with spec_lineage_id, plan_version, sentinel_session_id, rotated_at [REQ: lineage-tagging-on-all-history-records, scenario: rotated-event-files]
- [x] AC-34: WHEN coverage/e2e/worktree history appenders write a line THEN the JSON includes spec_lineage_id [REQ: lineage-tagging-on-all-history-records, scenario: coverage-history-line]

### Lineage-filtered APIs
- [x] AC-35: WHEN /api/<project>/activity-timeline?lineage=v1.md is called AND live is v2 THEN only v1-tagged spans are returned [REQ: lineage-filtering-on-the-activity-timeline, scenario: filter-to-v1-while-v2-runs-live]
- [x] AC-36: WHEN the endpoint is called without a lineage parameter THEN response equals ?lineage=<state.spec_lineage_id> [REQ: lineage-filtering-on-the-activity-timeline, scenario: lineage-parameter-omitted]
- [x] AC-37: WHEN /api/<project>/state?lineage=v1.md is called AND live is v2 THEN token totals include only v1-tagged changes, no v2 contamination [REQ: token-endpoints-honour-lineage-filter, scenario: v1-totals-while-v2-runs]
- [x] AC-38: WHEN /api/<project>/llm-calls?lineage=v1.md is called THEN the call list contains only v1-tagged calls [REQ: token-endpoints-honour-lineage-filter, scenario: llm-calls-filtered-by-lineage]
- [x] AC-39: WHEN /api/<project>/digest?lineage=v1.md is called THEN Reqs/AC/E2E consider only v1-tagged records [REQ: coverage-history-carries-lineage, scenario: v1-coverage-snapshot-while-v2-runs]
- [x] AC-40: WHEN REQ-X was merged under v1 and never re-merged under v2 AND /digest?lineage=v2 is requested THEN REQ-X is reported uncovered under v2 [REQ: coverage-history-carries-lineage, scenario: req-covered-in-v1-but-not-v2]
- [x] AC-41: WHEN /api/<project>/digest/e2e?lineage=v1.md is called THEN only v1-tagged manifest blocks contribute [REQ: e2e-manifest-history-carries-lineage, scenario: v1-e2e-manifest-while-v2-is-running]

### Lineage selector endpoints + UI
- [x] AC-42: WHEN GET /api/<project>/lineages is called AND archive has v1 entries AND live is v2 THEN response contains both with metadata (display_name, first/last_seen_at, is_live, change_count, merged_count) [REQ: lineages-listing-endpoint, scenario: two-lineages-present]
- [x] AC-43: WHEN no record carries spec_lineage_id THEN response contains a single synthetic `__legacy__` lineage entry [REQ: lineages-listing-endpoint, scenario: no-lineage-tags-legacy-project]
- [x] AC-44: WHEN data endpoints receive ?lineage=__all__ THEN the unfiltered union is returned with each record retaining its spec_lineage_id [REQ: data-endpoints-accept-an-optional-lineage-filter, scenario: all-lineages-merged-view]
- [ ] AC-45: WHEN dashboard loads first time AND exactly one lineage has is_live=true THEN that lineage is selected AND its sidebar entry is highlighted [REQ: left-sidebar-lineage-list, scenario: default-selection-on-first-load]
- [ ] AC-45a: WHEN dashboard loads AND no lineage has is_live=true THEN the lineage with the newest last_seen_at is selected [REQ: left-sidebar-lineage-list, scenario: default-when-no-lineage-is-live]
- [ ] AC-46: WHEN operator clicks v1.md in the sidebar while v2 runs THEN every tab refetches with ?lineage=v1.md AND sentinel continues on v2 AND live-indicator dot stays on v2 [REQ: left-sidebar-lineage-list, scenario: switching-lineage]
- [ ] AC-46a: WHEN viewing v1.md while sentinel runs v2.md THEN StatusHeader badge reflects v2 AND hint text "Viewing v1.md — sentinel running v2.md" appears [REQ: left-sidebar-lineage-list, scenario: live-badge-decouples-from-view]
- [ ] AC-47: WHEN operator selects v1.md and reloads THEN selection restores from localStorage; if lineage missing it falls back to default-selection rule [REQ: left-sidebar-lineage-list, scenario: selector-persistence]
- [ ] AC-48: WHEN "All lineages" is clicked THEN tables tag rows with lineage, Phases shows a section per lineage, sidebar highlights the "All lineages" entry [REQ: left-sidebar-lineage-list, scenario: all-lineages-mode]

### Lineage-scoped coverage
- [x] AC-49: WHEN v2 lineage spec declares 3 REQs AND a v2 change merges satisfying all 3 THEN v2 coverage reports 3/3 = 100% AND v1's 120 REQs do NOT appear in v2 response [REQ: coverage-denominator-is-the-lineages-own-spec, scenario: v2-delivers-a-single-new-screen-on-top-of-v1]
- [ ] AC-50: WHEN v1 delivered /admin AND v2 spec references REQ-ADMIN-001 AND no v2 change has touched it THEN v2 coverage reports REQ-ADMIN-001 uncovered (no filesystem-based auto-mark) [REQ: coverage-denominator-is-the-lineages-own-spec, scenario: pre-existing-code-does-not-pre-fill-coverage]
- [x] AC-51: WHEN v1 spec defined A,B,C AND v2 spec defines only B THEN v2 coverage denominator is {B} AND A+C do not appear in v2 response [REQ: coverage-denominator-is-the-lineages-own-spec, scenario: lineage-spec-defines-subset-of-prior-spec]
