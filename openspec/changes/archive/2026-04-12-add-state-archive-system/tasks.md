# Tasks: add-state-archive-system

## 1. Backend — Change Journal (Part 1)

**Goal:** hook `update_change_field()` to append per-change JSONL history without breaking the hot path. No new module-level imports in `state.py` beyond stdlib. Path derived purely from the `state_file` argument.

- [x] 1.1 Define `_JOURNALED_FIELDS: frozenset[str]` at module level in `lib/set_orch/state.py` containing the 21 fields enumerated in the `change-journal` spec (gate results, gate outputs, gate timings, `retry_context`, `status`, `current_step`) [REQ: centralized-journaled-fields-list]
- [x] 1.2 Add module-level `_JOURNAL_SEQ_CACHE: dict[str, int]` in `state.py` to cache the per-journal-file monotonic sequence number (avoids re-reading the file to find the next seq) [REQ: journal-entry-format]
- [x] 1.3 Implement `_journal_path(state_file: str, change_name: str) -> str` in `state.py` returning `os.path.join(os.path.dirname(state_file), "journals", f"{change_name}.jsonl")`. NO SetRuntime call. NO subprocess. NO paths.py import [REQ: journal-append-on-field-overwrite]
- [x] 1.4 Implement `_append_journal(state_file, change_name, field, old_value, new_value)` in `state.py` that: (a) computes the journal path, (b) ensures the parent dir exists (`os.makedirs(..., exist_ok=True)`), (c) increments and caches `_JOURNAL_SEQ_CACHE[path]`, (d) builds the JSON line, (e) opens the file with `open(path, "ab")`, acquires `fcntl.flock(f.fileno(), LOCK_EX)`, writes the line, releases the lock, closes. [REQ: journal-entry-format]
- [x] 1.5 In `_append_journal`, wrap the JSON serialization in a try/except that falls back to `json.dumps(..., default=str)` and further catches `UnicodeEncodeError` by stringifying with `repr()`, so no exotic value type can break the write [REQ: journal-entry-format]
- [x] 1.6 Hook `_append_journal` into `update_change_field()` INSIDE the `locked_state` block, placed IMMEDIATELY after the `logger.info("State update: %s.%s = %r (was: %r)")` line (state.py ~line 499), guarded by `field_name in _JOURNALED_FIELDS and value != old_value`. This position ensures the hook only runs for actual changes and that the old/new values are still in scope. [REQ: journal-append-on-field-overwrite]
- [x] 1.7 Wrap the hook call in a `try: ... except BaseException as exc: logger.warning("_append_journal failed for %s.%s: %s", change_name, field_name, exc)`. Catching `BaseException` (not `Exception`) is deliberate — journal append must never, under any circumstance, propagate an exception out of `update_change_field` [REQ: non-blocking-journal-writes]
- [x] 1.8 Verify `state.py` still imports only stdlib + `.events` (TYPE_CHECKING only) — no new imports. Run `python -c "from lib.set_orch import state"` to confirm clean import [REQ: journal-append-on-field-overwrite]
- [x] 1.9 Add unit test `tests/unit/test_state_journal.py` using `tempfile.TemporaryDirectory` only (no live state). Cover: (a) overwrite produces entry, (b) no-op write produces none, (c) non-journaled field produces none, (d) first write with null old value produces `old: null`, (e) unwritable journal dir logs warning and state update still commits, (f) value containing a Path object serializes via `default=str` fallback [REQ: journal-append-on-field-overwrite]
- [x] 1.10 Add unit test: spawn two threads both calling `update_change_field` with the same state_file+change name, assert both lines are in the journal (thread safety under the state lock) [REQ: non-blocking-journal-writes]
- [x] 1.11 Add unit test: assert `_JOURNAL_SEQ_CACHE` increments monotonically within a single test invocation and resets between tests [REQ: journal-entry-format]
- [x] 1.12 Implement `GET /api/{project}/changes/{name}/journal` in `lib/set_orch/api/orchestration.py` after the existing `/changes/{name}` route. Derive `journal_path` from the resolved state_file (same rule as `_journal_path`). Read JSONL, parse, compute `grouped` view [REQ: journal-api-endpoint]
- [x] 1.13 In the grouping logic: iterate entries chronologically, open a "run" whenever we see a `*_result` entry for a gate, attach the matching `*_output` and `gate_*_ms` entries that share a timestamp (±2s window to tolerate clock drift between the 3 writes in gate_runner.py L327-332). Each closed run becomes one entry in `grouped[gate]` [REQ: journal-api-endpoint]
- [x] 1.14 Handle missing journal file (return `{"entries": [], "grouped": {}}` with HTTP 200) and missing change name in state.json (HTTP 404) [REQ: journal-api-endpoint]
- [x] 1.15 Add API test using FastAPI `TestClient`: POST state updates via `update_change_field`, then GET `/journal` and assert the response shape [REQ: journal-api-endpoint]

## 2. Backend — File Archive Helper (Part 2)

**Goal:** provide a reusable archive-before-overwrite helper and apply it to 3 call sites without regressing their write behavior on helper failure.

- [x] 2.1 Create `lib/set_orch/archive.py` with module-level docstring, logger, stdlib imports only (`json`, `os`, `shutil`, `tempfile`, `datetime`, `pathlib`, `logging`) plus `from .git_utils import run_git` (already exists) [REQ: archive-before-overwrite-helper]
- [x] 2.2 Implement `archive_and_write(path, content, *, archive_dir, reason=None, max_archives=None)` — note the explicit `archive_dir` kwarg; the helper does NOT guess paths, callers pass them explicitly [REQ: archive-before-overwrite-helper]
- [x] 2.3 Step 1: if target `path` exists, archive it. Compute archive filename as `<UTC-YYYYMMDDTHHMMSSZ><suffix>`, ensure `archive_dir` exists, `shutil.copy2(path, archive_dir/filename)`. If archiving raises, log WARNING and continue to the write (data preservation beats metadata) [REQ: archive-before-overwrite-helper]
- [x] 2.4 Step 2: write new content atomically — `tempfile.NamedTemporaryFile` in the same dir as `path`, write content, `os.replace(tmp, path)`. If this step raises, propagate (the caller's error handling must take over) [REQ: atomic-write-semantics]
- [x] 2.5 Step 3 (only if archiving step 1 succeeded AND `reason` is set): write `<archive>.meta.json` sidecar with `{reason, ts, commit}`. Resolve `commit` by calling `run_git("rev-parse", "HEAD", cwd=os.path.dirname(path), timeout=2)`, catching any exception and storing `null`. Sidecar write failures are logged WARNING [REQ: archive-metadata-sidecar]
- [x] 2.6 Step 4 (only if `max_archives` is set): glob `archive_dir/*<suffix>`, sort by name (timestamp-encoded = chronological), unlink entries beyond `max_archives`. Failures log WARNING [REQ: optional-rolling-retention]
- [x] 2.7 Add unit test `tests/unit/test_archive.py` using `tempfile.TemporaryDirectory`. Cover: (a) write to new file skips archive step, (b) write to existing file produces snapshot + new content, (c) sidecar written when reason given, (d) sidecar NOT written when reason is None, (e) `max_archives=3` keeps only 3 newest, (f) `max_archives=None` keeps unlimited, (g) archiving failure does not prevent write (simulate via read-only archive_dir), (h) write failure propagates [REQ: archive-before-overwrite-helper]
- [x] 2.8 Add unit test: git commit resolver returns `null` when cwd is not a git repo (use `tempfile.TemporaryDirectory` not inside any git repo) [REQ: archive-metadata-sidecar]
- [x] 2.9 Migrate `lib/set_orch/sentinel/findings.py::_write()`: wrap the existing write logic as `_write_direct()`, then define the new `_write()` that calls `archive_and_write(path, content, archive_dir=self.rt.sentinel_archive_dir, reason="findings-update")` with a try/except that falls back to `_write_direct()` on failure and logs WARNING. This preserves the "never lose findings" invariant [REQ: sentinel-findings-use-archive-helper]
- [x] 2.10 Migrate `lib/set_orch/sentinel/status.py::_write()`: same pattern, `reason="status-update", max_archives=20`. Status writes are frequent (every heartbeat); retention prevents the archive from growing unbounded [REQ: sentinel-status-use-archive-helper-with-retention]
- [x] 2.11 Migrate `lib/set_orch/engine.py` spec-coverage-report.md regeneration (~line 2617): same pattern, `reason="coverage-regen"`, fallback to direct write [REQ: coverage-report-use-archive-helper]
- [x] 2.12 Verify: existing `sentinel_archive_dir` property in paths.py (line 172-173) already returns `<sentinel_dir>/archive`. The helper will write to `<sentinel_archive_dir>/findings/<ts>.json` — update the property or pass `<sentinel_archive_dir>/findings` explicitly. Choose: explicit sub-path in caller to keep paths.py unchanged [REQ: sentinel-findings-use-archive-helper]
- [x] 2.13 Add integration test `tests/integration/test_archive_integration.py`: call `SentinelFindings().add()` three times against a temp runtime, assert three snapshots accumulate in the archive [REQ: sentinel-findings-use-archive-helper]
- [x] 2.14 Add integration test: call `SentinelStatus().heartbeat()` 25 times against a temp runtime, assert exactly 20 snapshots remain [REQ: sentinel-status-use-archive-helper-with-retention]

## 3. Backend — Worktree Harvest (Part 3)

**Goal:** copy valuable worktree-local files to a persistent archive on every successful merge. Runs inside `cleanup_worktree()` wrapped in try/except so harvest failure never blocks a merge.

- [x] 3.1 Create `lib/set_orch/worktree_harvest.py` with module docstring, logger, stdlib imports (`json`, `os`, `shutil`, `datetime`, `pathlib`, `logging`) plus `from .git_utils import run_git` [REQ: post-merge-worktree-harvest]
- [x] 3.2 Define `HARVEST_ARTIFACTS: list[tuple[str, bool]]` with `(".set/reflection.md", True), (".set/loop-state.json", True), (".set/activity.json", True), (".claude/review-findings.md", True)` — all optional [REQ: post-merge-worktree-harvest]
- [x] 3.3 Implement `harvest_worktree(change_name: str, wt_path: str, project_path: str, *, reason: str = "merge") -> Path | None` [REQ: post-merge-worktree-harvest]
- [x] 3.4 Resolve destination via `SetRuntime(project_path=project_path)` (merger.py already does this pattern safely — it's not on a hot path, only runs on merge completion). `dest_root = Path(rt.orchestration_dir) / "archives" / "worktrees" / change_name` [REQ: harvest-destination-path]
- [x] 3.5 Collision handling: if `dest_root.exists()`, compute `ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")`, set `dest_root = dest_root.with_name(f"{change_name}.{ts}")`, log WARNING [REQ: harvest-destination-path]
- [x] 3.6 Create `dest_root` with `mkdir(parents=True, exist_ok=True)` [REQ: post-merge-worktree-harvest]
- [x] 3.7 Iterate `HARVEST_ARTIFACTS`: for each `(rel, optional)`, check if `Path(wt_path) / rel` exists. If yes, `shutil.copy2` to `dest_root / Path(rel).name` (flattened, no subdirs). Record harvested paths in a list. If missing and optional, skip silently. If missing and NOT optional, log WARNING (none are non-optional in v1, but the flag is there for future use) [REQ: post-merge-worktree-harvest]
- [x] 3.8 Resolve HEAD commit: `commit = run_git("rev-parse", "HEAD", cwd=wt_path, timeout=2)` wrapped in try/except returning `None` on failure [REQ: harvest-metadata-sidecar]
- [x] 3.9 Write `.harvest-meta.json` in `dest_root` with `json.dumps({"harvested_at": datetime.utcnow().isoformat() + "Z", "reason": reason, "wt_path": wt_path, "wt_name": change_name, "files": harvested, "commit": commit}, indent=2)` [REQ: harvest-metadata-sidecar]
- [x] 3.10 Log INFO: `"Harvested %d files from %s to %s", len(harvested), change_name, dest_root` [REQ: post-merge-worktree-harvest]
- [x] 3.11 Return `dest_root` [REQ: post-merge-worktree-harvest]
- [x] 3.12 Integrate into `lib/set_orch/merger.py::cleanup_worktree()` immediately after the `_archive_test_artifacts(change_name, wt_path, project_path)` call and BEFORE the retention policy check. The call is: `try: harvest_worktree(change_name, wt_path, project_path) except Exception: logger.warning("Worktree harvest failed for %s", change_name, exc_info=True)` [REQ: non-blocking-harvest]
- [x] 3.13 Add unit test `tests/unit/test_worktree_harvest.py` using `tempfile.TemporaryDirectory`. Cover: (a) all 4 files present → all copied, (b) only 2 files present → 2 copied, files list reflects it, (c) destination exists → timestamped fallback used with WARNING log asserted, (d) `.harvest-meta.json` schema matches, (e) `commit` is `None` when wt_path is not a git repo [REQ: post-merge-worktree-harvest]
- [x] 3.14 Add unit test: simulate `harvest_worktree` raising (mock `shutil.copy2` to raise), assert the caller's try/except in `cleanup_worktree` swallows it [REQ: non-blocking-harvest]
- [x] 3.15 Add integration test `tests/integration/test_harvest_on_merge.py`: create a temp git repo with a worktree that contains the 4 files, simulate a successful merge by calling `cleanup_worktree()` directly, assert the harvest directory contains the expected files [REQ: post-merge-worktree-harvest]

## 4. Frontend — Gate History Sub-tabs (Part 4)

**Goal:** the dashboard reads journal data and renders per-run sub-tabs. Does NOT touch backend. Deployed LAST so any backend issue can be verified without the frontend being in the way.

- [x] 4.1 Add `JournalEntry` type to `web/src/lib/api.ts` matching `{ts: string; field: string; old: unknown; new: unknown; seq: number}` [REQ: journal-fetcher-in-web-api-client]
- [x] 4.2 Add `GateRun` type to `web/src/lib/api.ts` matching `{run: number; result: "pass" | "fail" | "skip"; output?: string; ts: string; ms: number}` [REQ: journal-fetcher-in-web-api-client]
- [x] 4.3 Add `ChangeJournal` type: `{ entries: JournalEntry[]; grouped: Record<string, GateRun[]> }` [REQ: journal-fetcher-in-web-api-client]
- [x] 4.4 Add `getChangeJournal(project: string, name: string): Promise<ChangeJournal>` fetcher in `web/src/lib/api.ts`. On non-2xx response, reject with an Error containing the change name [REQ: journal-fetcher-in-web-api-client]
- [x] 4.5 In `web/src/components/LogPanel.tsx`, rename the "Task" sub-tab label to "Session". Keep the internal tab id `task` unchanged so URL state / keyboard shortcuts keep working [REQ: bottom-panel-session-tab-rename]
- [x] 4.6 Add `journal` state to `LogPanel`: `const [journal, setJournal] = useState<ChangeJournal | null>(null)`. Fetch in a `useEffect` keyed on `change.name`; on error, `setJournal(null)` so the legacy fallback path runs [REQ: gate-history-sub-tabs-from-journal]
- [x] 4.7 Extend `buildGateTabs()` (LogPanel.tsx ~L127) to accept the journal as a second argument and, for each gate with `grouped[gate].length > 0`, attach a `runs: GateRun[]` field alongside the existing `result`/`output`/`ms` legacy fields [REQ: gate-history-sub-tabs-from-journal]
- [x] 4.8 Add `activeRunIndex: Record<string, number>` state in `LogPanel`, keyed by gate id. Default each gate to the last run (`runs.length - 1`) when journal first arrives [REQ: gate-history-sub-tabs-from-journal]
- [x] 4.9 Below the existing gate sub-tab bar (LogPanel.tsx ~L312-346) and ABOVE the `GateOutputPane` render (~L138-157), insert a secondary sub-tab row that renders only when the selected gate has a non-empty `runs` array. One button per run: `[Run N ✓/✗/⊘]`. Clicking sets `activeRunIndex[gate.id]` to that run [REQ: gate-history-sub-tabs-from-journal]
- [x] 4.10 Modify the `GateOutputPane` props so it can receive a `GateRun` source when journal data is present. When `activeRunIndex` is set and `runs[activeRunIndex]` exists, pass that run's `{result, output, ms, ts}` to the pane. Otherwise fall back to the legacy `ChangeInfo` fields exactly as today [REQ: gate-history-sub-tabs-from-journal]
- [x] 4.11 Legacy fallback: when `journal === null` OR `grouped[gate] === undefined` OR `grouped[gate].length === 0`, render NO sub-tab row and use the legacy `ChangeInfo`-based pane (zero change from today) [REQ: gate-history-sub-tabs-from-journal]
- [x] 4.12 Add Playwright E2E test `web/tests/e2e/gate-history-subtabs.spec.ts`. Use fixture data if a live project isn't available: mock the `/journal` endpoint response via `page.route()`. Cover: (a) Session label present, (b) sub-tab row with 3 buttons when grouped has 3 e2e runs, (c) clicking the second button updates the visible output text, (d) legacy fallback when grouped is empty — no sub-tab row visible [REQ: e2e-test-coverage]
- [x] 4.13 Run `cd web && pnpm build` — fails fast on TypeScript errors [REQ: e2e-test-coverage]
- [x] 4.14 Run `cd web && pnpm test:e2e --grep gate-history` against any available project to exercise the new test [REQ: e2e-test-coverage]

## 5. Supervisor — Transition-Based Triggers (Part 5)

**Goal:** eliminate steady-state trigger re-firing and skip-event spam. Observed on minishop-run-20260412-0103 where `integration_failed` emitted 200+ `skipped: retry_budget_exhausted` events over 7.5h before manual intervention.

- [x] 5.1 Add `last_change_statuses: dict[str, str] = field(default_factory=dict)` to `SupervisorStatus` in `lib/set_orch/supervisor/state.py`. The field persists per-change last-observed status and survives daemon restart [REQ: per-change-last-observed-status-in-supervisorstatus]
- [x] 5.2 Extend `AnomalyContext` in `lib/set_orch/supervisor/anomaly.py` with a `last_change_statuses: dict[str, str]` field AND a `last_orch_status: str` field. Both are populated by `daemon._build_anomaly_context()` from `self.status.last_change_statuses` [REQ: transition-based-anomaly-triggers-not-steady-state]
- [x] 5.3 In `detect_integration_failed`, derive `prev = ctx.last_change_statuses.get(change_name, "")` and only yield a trigger when `current != prev AND "failed" in current`. This means a change moving from `running` → `failed` triggers, but `failed` → `failed` does not [REQ: transition-based-anomaly-triggers-not-steady-state, status-first-transitions-to-failed, status-remains-failed-across-polls]
- [x] 5.4 In `detect_terminal_state`, derive `prev = ctx.last_orch_status` and only yield a trigger when `current != prev AND current in TERMINAL_STATUSES AND not ctx.orchestrator_alive`. A restart against a pre-existing terminal state is silent [REQ: transition-detection-for-non-change-scoped-triggers, orchestration-in-terminal-state-across-multiple-polls]
- [x] 5.5 In `detect_token_stall`, add a transition check: only fire when the (change, crossed_threshold) tuple was NOT already in a `crossed_token_stall_thresholds: set[str]` field on SupervisorStatus. Once fired, add to the set so subsequent polls with the same conditions skip [REQ: token-stall-detector-transition-aware, change-stuck-at-600k-tokens-with-no-state-movement]
- [x] 5.6 In `daemon._scan_and_dispatch_anomalies`, AFTER detectors run, update `self.status.last_change_statuses` from the current state's changes. Persist via the existing `write_status()` call at the end of the poll [REQ: transition-based-anomaly-triggers-not-steady-state]
- [x] 5.7 Unit test `test_supervisor_anomaly.py::TestTransitionTriggers`: (a) empty `last_change_statuses` + `failed` current → fires (first observation), (b) `last_change_statuses[x]=failed` + `failed` current → no fire, (c) `last_change_statuses[x]=running` + `failed` current → fires, (d) `last_change_statuses[x]=failed` + `done` current → no fire, (e) `last_change_statuses[x]=failed` + `running` current → no fire, (f) `last_change_statuses[x]=running` + `running` current → no fire [REQ: transition-based-anomaly-triggers-not-steady-state]
- [x] 5.8 Unit test for `detect_terminal_state`: (a) orch dead + `done` + prev `running` → fires, (b) orch dead + `done` + prev `done` → no fire, (c) orch alive + `done` → no fire (existing behavior) [REQ: transition-detection-for-non-change-scoped-triggers]
- [x] 5.9 Unit test for daemon restart persistence: write status.json with `last_change_statuses={"x": "failed"}`, construct a new daemon, verify the first poll does NOT re-fire `integration_failed` for `x` if its status is still `failed` [REQ: daemon-restart-mid-run-with-a-pre-existing-failed-change]

## 6. Issues — Merge-Unblock Auto-Resolve (Part 6)

**Goal:** merge queue never locks on stale `diagnosed` issues. Manual registry edits during minishop-run-20260412-0103 must not be required again.

- [x] 6.1 Add `diagnosed_at: Optional[str]` field to the issue dataclass in `lib/set_orch/issues/models.py`. Set it during the `investigating → diagnosed` transition [REQ: diagnosed-state-timeout-as-safety-net]
- [x] 6.2 Implement `auto_resolve_for_change(change_name: str, reason: str = "change_merged_auto_resolve") -> list[str]` in `lib/set_orch/issues/audit.py` (or a new `lib/set_orch/issues/registry.py`). Loads `.set/issues/registry.json`, finds all issues with `affected_change == change_name AND state not in ("fixed", "wont_fix")`, transitions each to `fixed`, appends audit entries, writes the registry atomically. Returns the list of resolved issue IDs [REQ: issue-ownership-self-resolves-on-change-merge]
- [x] 6.3 In `lib/set_orch/merger.py::merge_change()`, after the successful merge has been committed to state.json (line ~691 where `status=merged` is set), call `auto_resolve_for_change(change_name, reason="merge_success:" + change_name)` wrapped in try/except [REQ: auto-resolve-is-non-blocking-best-effort]
- [x] 6.4 The try/except must log WARNING with the change name, attempted issue IDs (if known), and the underlying exception. It must NOT raise [REQ: registry-file-is-unwritable-during-merge]
- [x] 6.5 Add a `DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS = 3600` constant in `lib/set_orch/issues/models.py` [REQ: diagnosed-state-timeout-as-safety-net]
- [x] 6.6 Add a periodic check in the engine monitor loop (or a new `lib/set_orch/issues/watchdog.py`): iterate issues with `state == "diagnosed"`, compute `age = now - diagnosed_at`, if `age > DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS` emit `ISSUE_DIAGNOSED_TIMEOUT` event with `{issue_id, change, age_seconds}`. Log WARNING [REQ: issue-stuck-in-diagnosed-for-over-1-hour]
- [x] 6.7 Add `ISSUE_DIAGNOSED_TIMEOUT` to `KNOWN_EVENT_TYPES` in `lib/set_orch/supervisor/anomaly.py` so the supervisor doesn't fire `unknown_event_type` [REQ: issue-stuck-in-diagnosed-for-over-1-hour]
- [x] 6.8 Add `POST /api/{project}/issues/{iss_id}/resolve` endpoint in `lib/set_orch/api/sentinel.py` or a new `lib/set_orch/api/issues.py`. Accepts `{"reason": str}` body, calls the audit helper, returns `{"status": "ok", "iss_id": ..., "new_state": "fixed"}` on success, HTTP 404 when issue missing [REQ: manager-api-to-resolve-issues]
- [x] 6.9 Unit test `tests/unit/test_issues_auto_resolve.py`: (a) resolve single diagnosed issue, (b) resolve multiple issues on same change, (c) cross-change issues untouched, (d) registry write failure logs WARNING, (e) empty registry → no-op [REQ: issue-ownership-self-resolves-on-change-merge, change-has-multiple-issues-some-still-investigating, cross-change-issues-are-not-auto-resolved, registry-file-is-unwritable-during-merge]
- [x] 6.10 Integration test: simulate a `merge_change()` call where 2 diagnosed issues exist, assert both become `fixed` and the merge status change is preserved [REQ: change-merges-while-an-issue-is-in-diagnosed-state]
- [x] 6.11 API test `tests/unit/test_api_issues_resolve.py`: POST with reason → 200 + state change, POST with unknown iss_id → 404 [REQ: operator-manually-resolves-a-stuck-issue, attempt-to-resolve-a-non-existent-issue]
- [x] 6.12 Update `openspec/changes/add-state-archive-system/design.md` with a decision note on why auto-resolve uses the merge status change as the trigger (instead of, say, the MERGE_SUCCESS event) — centralization on `merge_change()` makes the hook resilient to event-bus failure

## 7. Dispatcher — Ralph Input Refresh (Part 7)

**Goal:** in-flight changes pick up learnings from sibling changes that merged during their ralph loop. The refresh is gated by mtime comparison so it's a no-op when nothing has changed.

- [x] 7.1 Add `_maybe_refresh_input_md(change_name: str, state_path: str, wt_path: str) -> bool` in `lib/set_orch/dispatcher.py` that: (a) computes `input_md_path` the same way as `_initialize_openspec_change`, (b) checks if the file exists and what its mtime is, (c) computes `learnings_path = <project>/set/orchestration/review-learnings.jsonl`, (d) compares mtimes, (e) if learnings is newer, calls the existing `_build_input_content()` pipeline with the current state/ctx and rewrites the file via atomic replace, (f) returns `True` if refreshed, `False` if not [REQ: ralph-loop-regenerates-input-md-on-iteration-transition]
- [x] 7.2 Hook point 1: in `lib/set_orch/loop_state.py::record_iteration_end()` (or equivalent — the site where the ralph loop bumps `current_iteration` in `loop-state.json`), call the refresh helper with the change's worktree path [REQ: ralph-loop-regenerates-input-md-on-iteration-transition]
- [x] 7.3 Hook point 2: in `lib/set_orch/dispatcher.py` or `lib/set_orch/engine.py`, during the "reattach to existing worktree on supervisor restart" code path, call the refresh helper BEFORE the ralph loop resumes [REQ: supervisor-restart-preserves-and-refreshes-input-context]
- [x] 7.4 Add `refresh_input_on_learnings_update: bool = True` to the Directives dataclass in `lib/set_orch/dispatcher.py`. Parse in `parse_directives`. The refresh helper checks the directive at the start and early-returns if disabled [REQ: refresh-is-opt-out-safe]
- [x] 7.5 Log INFO at every refresh: `logger.info("Input refresh for %s iter %d — learnings mtime %s > input mtime %s", ...)`. Log INFO at every skip when mtimes are compared: `logger.debug("Input refresh skipped for %s — learnings not newer", ...)` [REQ: refresh-is-opt-out-safe]
- [x] 7.6 Unit test `tests/unit/test_dispatcher_input_refresh.py`: (a) learnings file newer than input.md → refresh happens, (b) learnings file older than input.md → no refresh, (c) learnings file missing → no refresh, (d) input.md missing → no refresh (not initialized yet; that's the initial-dispatch path's job), (e) directive disabled → no refresh even when mtime would trigger [REQ: learnings-update-while-change-is-in-ralph-loop, no-learnings-update-since-last-iteration, first-iteration-always-gets-fresh-input, operator-disables-the-feature]
- [x] 7.7 Integration test: simulate two sequential merges with ralph loops; verify the second loop's input.md contains learnings from the first merged change

## 8. Review + Classifier — Severity Calibration (Part 8)

**Goal:** CRITICAL reserved for crash/leak/data-loss. Convention violations and UI polish are MEDIUM/LOW, not merge-blockers.

- [x] 8.1 Add a Severity Rubric section to `lib/set_orch/templates.py::render_review_prompt()`. Exact text: see spec at `specs/review-severity-calibration/spec.md` Scenario "Review prompt explicitly lists severity examples" — the rubric is the authoritative copy [REQ: explicit-severity-rubric-in-review-prompt]
- [x] 8.2 Include the "When in doubt between two tiers, pick the LOWER one" guidance immediately after the rubric [REQ: explicit-severity-rubric-in-review-prompt]
- [x] 8.3 Add a condensed rubric to `lib/set_orch/llm_verdict.py::_build_classifier_prompt()` as a new SCOPE rule (alongside the existing `scope_context` filter). The classifier's rubric is the same tiering but without the examples — just the short definitions [REQ: classifier-rubric-matches-review-prompt]
- [x] 8.4 Add `downgrades: list[dict] = field(default_factory=list)` to `GateVerdict` dataclass in `lib/set_orch/gate_verdict.py`. Each entry: `{from: str, to: str, summary: str}` [REQ: severity-downgrade-audit-trail]
- [x] 8.5 Update `classify_verdict()` to populate `downgrades` when the classifier lowers a tag below its reviewer-assigned severity. The JSON schema sent to the classifier gains a `downgrades` field; the classifier is instructed to list every downgrade it performs [REQ: severity-downgrade-audit-trail]
- [x] 8.6 Update `_persist_review_verdict()` in `lib/set_orch/verifier.py` to include `downgrades` in the sidecar write [REQ: severity-downgrade-audit-trail]
- [x] 8.7 Update `review_change()` retry-prompt assembly to group findings by severity: `## Must Fix` (CRITICAL + HIGH), `## Should Fix (if trivial)` (MEDIUM), `## Nice to Have` (LOW). Pass this grouped text as `prompt_prefix` on retry [REQ: agents-fix-prompts-reflect-severity]
- [x] 8.8 If zero LOW findings, skip the "Nice to Have" section. If zero MEDIUM, skip "Should Fix". If only CRITICAL/HIGH, render only "Must Fix" [REQ: retry-prompt-with-only-critical]
- [x] 8.9 Unit test `tests/unit/test_verifier.py::TestSeverityRubric`: feed a mock review output with mixed severity tags, verify the classifier downgrade logic works when the rubric says CRITICAL is wrong [REQ: classifier-sees-a-review-text-with-mismatched-severity]
- [x] 8.10 Unit test for retry prompt grouping: given a findings list, verify the prompt_prefix is structured correctly with the right sections [REQ: retry-prompt-with-mixed-severities]
- [x] 8.11 Integration test: run `review_change()` against a fixture review text with 1 CRITICAL + 2 MEDIUM, assert the sidecar has `verdict=fail, critical_count=1, medium_count=2, downgrades=[]` [REQ: classifier-sees-a-review-text-with-unclear-severity-tags]

## 9. Supervisor — Permanent Error Detection (Part 9)

**Goal:** spec-path typos and missing binaries halt immediately instead of burning the rapid-crash budget. Dashboard shows the error reason prominently.

- [x] 9.1 Define `PERMANENT_ERROR_SIGNALS: list[tuple[str, str]]` in `lib/set_orch/supervisor/anomaly.py` with the initial catalog from `specs/supervisor-permanent-errors/spec.md` — 8 entries covering spec_not_found, orchestrator_import_broken, orchestrator_binary_missing, directives_missing, state_file_missing, profile_resolution_failed [REQ: permanent-error-catalog-in-anomaly-module]
- [x] 9.2 Implement `_classify_exit(stderr_tail: str) -> Optional[str]` in `lib/set_orch/supervisor/anomaly.py` that iterates `PERMANENT_ERROR_SIGNALS` and returns the first matching reason code, or `None` [REQ: permanent-error-catalog-in-anomaly-module]
- [x] 9.3 In `lib/set_orch/supervisor/daemon.py::_restart_orchestrator()`, BEFORE the rapid-crash counter check: (a) read the last 2KB of the orchestrator's stderr log, (b) call `_classify_exit(tail)`, (c) if it returns a reason code, set `self._stop_reason = f"permanent_error:{code}"` + `self._permanent_error_tail = tail[-1024:]` + `self._stop_requested = True`, and return `False` [REQ: supervisor-distinguishes-permanent-errors-from-transient-crashes]
- [x] 9.4 Add `permanent_error: Optional[dict]` field to `SupervisorStatus` storing `{code, stderr_tail}`. Written in `_shutdown()` when `_stop_reason` starts with `permanent_error:` [REQ: manager-api-surfaces-permanent-errors-prominently]
- [x] 9.5 Update `lib/set_orch/api/_sentinel_orch.py::/sentinel/status` endpoint to include the `permanent_error` field when present, at top level of the response [REQ: dashboard-shows-permanent-error-after-spec-typo]
- [x] 9.6 Add a banner render in `web/src/pages/ProjectStatus.tsx` (or wherever the sentinel status panel lives) that shows `permanent_error.code` + a `Show details` expandable with `permanent_error.stderr_tail`. Red background. Render only when the field is present [REQ: dashboard-shows-permanent-error-after-spec-typo]
- [x] 9.7 Unit test `test_supervisor_anomaly.py::TestClassifyExit`: one test case per entry in `PERMANENT_ERROR_SIGNALS` verifying the pattern returns the expected reason code [REQ: unit-test-coverage-for-each-permanent-error-signal]
- [x] 9.8 Unit test: `_classify_exit("")` returns `None` [REQ: unknown-stderr-pattern]
- [x] 9.9 Unit test: `_classify_exit("Traceback (most recent call last):\n  File ...")` returns `None` (transient) [REQ: test-for-transient-python-traceback]
- [x] 9.10 Integration test: spawn a supervisor with a deliberate bad spec argument, verify it halts in < 5 seconds with `stop_reason: permanent_error:spec_not_found` and writes the expected status file [REQ: spec-file-not-found-on-first-start]

## Acceptance Criteria (from spec scenarios)

### change-journal

- [x] AC-1: WHEN `update_change_field()` is called with a field in `_JOURNALED_FIELDS` and the new value differs from the old value THEN a JSONL line is appended to `<orchestration_dir>/journals/<change-name>.jsonl` after the `locked_state` block exits [REQ: journal-append-on-field-overwrite, scenario: journaled-field-value-changes]
- [x] AC-2: WHEN the new value equals the old value THEN no journal entry is appended [REQ: journal-append-on-field-overwrite, scenario: journaled-field-value-unchanged-no-op-write]
- [x] AC-3: WHEN the field is NOT in `_JOURNALED_FIELDS` THEN no journal entry is appended [REQ: journal-append-on-field-overwrite, scenario: non-journaled-field-update]
- [x] AC-4: WHEN a journaled field is set for the first time (old is None) THEN a journal entry with `old: null` is written [REQ: journal-append-on-field-overwrite, scenario: first-write-no-prior-value]
- [x] AC-5: WHEN a journal entry is written THEN it contains exactly the keys `ts`, `field`, `old`, `new`, `seq` with `seq` monotonically increasing [REQ: journal-entry-format, scenario: entry-schema]
- [x] AC-6: WHEN the journal directory is unwritable THEN a WARNING is logged and the state update remains committed [REQ: non-blocking-journal-writes, scenario: journal-file-not-writable-permission-denied]
- [x] AC-7: WHEN two processes append to the journal concurrently THEN both lines are preserved without interleaving [REQ: non-blocking-journal-writes, scenario: concurrent-append-from-two-processes]
- [x] AC-8: WHEN `GET /api/{project}/changes/{name}/journal` is called THEN the response contains `entries` (chronological raw) and `grouped` (gate-keyed runs) [REQ: journal-api-endpoint, scenario: fetch-journal-for-a-change]
- [x] AC-9: WHEN the journal file is missing THEN the API returns `{"entries": [], "grouped": {}}` with HTTP 200 [REQ: journal-api-endpoint, scenario: journal-does-not-exist]
- [x] AC-10: WHEN the change is not in state.json THEN the API returns HTTP 404 [REQ: journal-api-endpoint, scenario: change-not-found]

### file-archive

- [x] AC-11: WHEN `archive_and_write()` targets an existing file THEN the old content is copied to `<archives_dir>/<relative-path>/<ts>.<ext>` before the new content is written atomically [REQ: archive-before-overwrite-helper, scenario: write-to-existing-file]
- [x] AC-12: WHEN `archive_and_write()` targets a new file THEN no archive is created and the new content is written atomically [REQ: archive-before-overwrite-helper, scenario: write-to-new-file]
- [x] AC-13: WHEN the write is interrupted THEN the original file remains intact because the archive was taken first [REQ: archive-before-overwrite-helper, scenario: atomic-write-semantics]
- [x] AC-14: WHEN `reason` is supplied THEN a `.meta.json` sidecar is written next to the archive with `reason`, `ts`, and `commit` [REQ: archive-metadata-sidecar, scenario: reason-supplied]
- [x] AC-15: WHEN no `reason` is supplied THEN no sidecar is written [REQ: archive-metadata-sidecar, scenario: no-reason-supplied]
- [x] AC-16: WHEN `max_archives=20` and the archive directory contains <20 snapshots THEN none are deleted [REQ: optional-rolling-retention, scenario: archive-count-below-limit]
- [x] AC-17: WHEN `max_archives=20` and the archive directory contains ≥20 snapshots THEN the oldest are pruned so exactly 20 remain [REQ: optional-rolling-retention, scenario: archive-count-exceeds-limit]
- [x] AC-18: WHEN `max_archives` is `None` THEN no snapshots are deleted regardless of count [REQ: optional-rolling-retention, scenario: no-retention-limit]
- [x] AC-19: WHEN `SentinelFindings` writes findings THEN the call goes through `archive_and_write(..., reason="findings-update")` [REQ: sentinel-findings-use-archive-helper, scenario: findings-update]
- [x] AC-20: WHEN `SentinelStatus.heartbeat()` writes status THEN the call goes through `archive_and_write(..., reason="status-update", max_archives=20)` [REQ: sentinel-status-use-archive-helper-with-retention, scenario: status-heartbeat]
- [x] AC-21: WHEN the engine regenerates `spec-coverage-report.md` THEN the call goes through `archive_and_write(..., reason="coverage-regen")` [REQ: coverage-report-use-archive-helper, scenario: coverage-report-regeneration]

### worktree-harvest

- [x] AC-22: WHEN `cleanup_worktree()` runs after a successful merge THEN `harvest_worktree()` copies `.set/reflection.md`, `.set/loop-state.json`, `.set/activity.json`, `.claude/review-findings.md` if present [REQ: post-merge-worktree-harvest, scenario: successful-merge-triggers-harvest]
- [x] AC-23: WHEN some harvested files are missing THEN they are silently skipped and the harvest completes with only present files [REQ: post-merge-worktree-harvest, scenario: worktree-missing-optional-files]
- [x] AC-24: WHEN all harvest candidates are missing THEN the destination directory is still created and `.harvest-meta.json` has `files: []` [REQ: post-merge-worktree-harvest, scenario: all-harvested-files-missing]
- [x] AC-25: WHEN the harvest directory for a change does not exist THEN the destination is `<orchestration_dir>/archives/worktrees/<change-name>/` [REQ: harvest-destination-path, scenario: first-harvest-for-a-change]
- [x] AC-26: WHEN the harvest directory already exists THEN the destination becomes `<change-name>.<UTC-timestamp>/` and a WARNING is logged [REQ: harvest-destination-path, scenario: collision-with-existing-harvest]
- [x] AC-27: WHEN a harvest completes THEN `.harvest-meta.json` contains `harvested_at`, `reason`, `wt_path`, `wt_name`, `files`, `commit` as valid JSON with 2-space indent [REQ: harvest-metadata-sidecar, scenario: metadata-contents]
- [x] AC-28: WHEN `harvest_worktree()` raises an exception THEN the merge cleanup proceeds, a WARNING is logged, and no state field is modified [REQ: non-blocking-harvest, scenario: harvest-throws-an-exception]
- [x] AC-29: WHEN `harvest_worktree()` succeeds THEN an INFO log records change name, destination path, and file count [REQ: non-blocking-harvest, scenario: harvest-runs-successfully]

### gate-history-view

- [x] AC-30: WHEN a user opens a change in the dashboard THEN the bottom-panel tab previously labeled "Task" now reads "Session" and its content is unchanged [REQ: bottom-panel-session-tab-rename, scenario: panel-renders]
- [x] AC-31: WHEN the user selects a gate tab for a change with 3 journal runs THEN a secondary sub-tab row appears with `[Run 1 ✗] [Run 2 ✗] [Run 3 ✓]` and the latest run is displayed by default [REQ: gate-history-sub-tabs-from-journal, scenario: journal-has-multiple-runs-for-a-gate]
- [x] AC-32: WHEN the user clicks a non-selected run sub-tab THEN the output pane updates without refetching or navigating [REQ: gate-history-sub-tabs-from-journal, scenario: switching-between-runs]
- [x] AC-33: WHEN a gate has exactly one run THEN a single sub-tab is rendered and the pane shows that run [REQ: gate-history-sub-tabs-from-journal, scenario: gate-has-only-one-run]
- [x] AC-34: WHEN a gate has no journal entries THEN no sub-tab row is rendered and the pane falls back to `ChangeInfo` fields [REQ: gate-history-sub-tabs-from-journal, scenario: gate-has-no-journal-entries-legacy-change]
- [x] AC-35: WHEN a developer imports `getChangeJournal` THEN its return type matches `{ entries: JournalEntry[]; grouped: Record<string, GateRun[]> }` [REQ: journal-fetcher-in-web-api-client, scenario: fetcher-signature-and-types]
- [x] AC-36: WHEN the backend returns 404 or 500 for the journal endpoint THEN the fetcher rejects and the LogPanel falls back to legacy view [REQ: journal-fetcher-in-web-api-client, scenario: journal-fetch-error]
- [x] AC-37: WHEN the Playwright test visits a change with 3 e2e runs in the journal THEN three sub-tab buttons are visible and clicking the second shows the second run's output [REQ: e2e-test-coverage, scenario: test-asserts-sub-tab-rendering-with-history]
- [x] AC-38: WHEN the Playwright test visits a change with an empty or missing journal THEN no sub-tab row renders and the pane shows the legacy single-run content [REQ: e2e-test-coverage, scenario: test-asserts-legacy-fallback]

### supervisor-transition-triggers

- [x] AC-39: WHEN a change's status transitions from `running` to `failed` THEN `detect_integration_failed` emits exactly one trigger for that change [REQ: transition-based-anomaly-triggers-not-steady-state, scenario: status-first-transitions-to-failed]
- [x] AC-40: WHEN a change's status remains `failed` across consecutive polls THEN no trigger is emitted and no skipped-event record is written [REQ: transition-based-anomaly-triggers-not-steady-state, scenario: status-remains-failed-across-polls]
- [x] AC-41: WHEN the daemon restarts and reads a persisted `last_change_statuses["x"] == "failed"` AND the current state still shows `x.status == failed` THEN no trigger fires on the first poll [REQ: per-change-last-observed-status-in-supervisorstatus, scenario: daemon-restart-mid-run-with-a-pre-existing-failed-change]
- [x] AC-42: WHEN the daemon observes a change it has never seen before AND that change's status matches a trigger condition THEN the trigger fires exactly once on that first observation [REQ: per-change-last-observed-status-in-supervisorstatus, scenario: fresh-daemon-sees-a-change-for-the-first-time]
- [x] AC-43: WHEN orchestration `state.status` transitions to `done` AND the orchestrator process is dead AND the daemon has not yet fired its `terminal_state` trigger THEN the trigger fires exactly once [REQ: transition-detection-for-non-change-scoped-triggers, scenario: orchestration-in-terminal-state-across-multiple-polls]
- [x] AC-44: WHEN a change first crosses the token-stall threshold AND has not moved state for the stall window THEN `detect_token_stall` fires once. Subsequent polls with the same numbers DO NOT re-fire [REQ: token-stall-detector-transition-aware, scenario: change-stuck-at-600k-tokens-with-no-state-movement]

### issue-merge-unblock

- [x] AC-45: WHEN a change merges successfully AND one of its issues is in `diagnosed` state THEN the issue is auto-transitioned to `fixed` with audit entry `change_merged_auto_resolve` [REQ: issue-ownership-self-resolves-on-change-merge, scenario: change-merges-while-an-issue-is-in-diagnosed-state]
- [x] AC-46: WHEN a change merges successfully AND multiple issues are attached to it THEN all tagged issues are resolved atomically [REQ: issue-ownership-self-resolves-on-change-merge, scenario: change-has-multiple-issues-some-still-investigating]
- [x] AC-47: WHEN a change merges successfully AND an open issue belongs to a DIFFERENT change THEN the other change's issue remains untouched [REQ: issue-ownership-self-resolves-on-change-merge, scenario: cross-change-issues-are-not-auto-resolved]
- [x] AC-48: WHEN the registry file cannot be updated during merge THEN a WARNING is logged with change name + issue IDs + error AND the merge itself remains committed [REQ: auto-resolve-is-non-blocking-best-effort, scenario: registry-file-is-unwritable-during-merge]
- [x] AC-49: WHEN an issue has been in `diagnosed` state for longer than `DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS` (default 3600) THEN the engine watchdog emits `ISSUE_DIAGNOSED_TIMEOUT` with issue_id, change, age_seconds [REQ: diagnosed-state-timeout-as-safety-net, scenario: issue-stuck-in-diagnosed-for-over-1-hour]
- [x] AC-50: WHEN an issue is resolved before the timeout fires THEN no timeout event is emitted [REQ: diagnosed-state-timeout-as-safety-net, scenario: issue-resolved-before-timeout]
- [x] AC-51: WHEN `POST /api/{project}/issues/{iss_id}/resolve` is called with a reason AND the issue exists THEN the issue transitions to `fixed` and the audit log records the operator rationale [REQ: manager-api-to-resolve-issues, scenario: operator-manually-resolves-a-stuck-issue]
- [x] AC-52: WHEN `POST /api/{project}/issues/{iss_id}/resolve` is called with a missing iss_id THEN HTTP 404 is returned with `{"error": "issue_not_found"}` [REQ: manager-api-to-resolve-issues, scenario: attempt-to-resolve-a-non-existent-issue]

### ralph-learnings-injection

- [x] AC-53: WHEN a ralph iteration ends AND the `review-learnings.jsonl` file mtime is newer than the change's `input.md` mtime THEN the dispatcher regenerates `input.md` and the next iteration sees the new learnings [REQ: ralph-loop-regenerates-input-md-on-iteration-transition, scenario: learnings-update-while-change-is-in-ralph-loop]
- [x] AC-54: WHEN a ralph iteration ends AND the learnings file mtime is older than input.md THEN no refresh happens [REQ: ralph-loop-regenerates-input-md-on-iteration-transition, scenario: no-learnings-update-since-last-iteration]
- [x] AC-55: WHEN a change is dispatched for the first time (iteration 1) THEN `input.md` is generated fresh exactly as today (no regression) [REQ: ralph-loop-regenerates-input-md-on-iteration-transition, scenario: first-iteration-always-gets-fresh-input]
- [x] AC-56: WHEN the supervisor daemon restarts AND reattaches to a still-running change's existing worktree THEN `input.md` is regenerated before the ralph loop resumes [REQ: supervisor-restart-preserves-and-refreshes-input-context, scenario: supervisor-restart-with-change-in-running-status]
- [x] AC-57: WHEN the supervisor restarts AND the worktree path no longer exists THEN the full re-dispatch path runs as today (no regression) [REQ: supervisor-restart-preserves-and-refreshes-input-context, scenario: worktree-missing-on-restart]
- [x] AC-58: WHEN two changes merge in quick succession THEN an in-flight third change's subsequent input.md regeneration includes learnings from both merged changes [REQ: cross-change-review-learnings-file-is-append-only, scenario: two-changes-merge-in-quick-succession]
- [x] AC-59: WHEN the `refresh_input_on_learnings_update: false` directive is set THEN the dispatcher never regenerates input.md after initial dispatch [REQ: refresh-is-opt-out-safe, scenario: operator-disables-the-feature]

### review-severity-calibration

- [x] AC-60: WHEN `render_review_prompt()` renders a review brief THEN the prompt contains a `## Severity Rubric` section with concrete examples for CRITICAL, HIGH, MEDIUM, LOW AND the "when in doubt pick lower" guidance [REQ: explicit-severity-rubric-in-review-prompt, scenario: review-prompt-explicitly-lists-severity-examples]
- [x] AC-61: WHEN the reviewer evaluates a raw `<button>` violation of shadcn rules THEN it is classified as MEDIUM and the gate passes [REQ: explicit-severity-rubric-in-review-prompt, scenario: reviewer-evaluates-a-shadcn-button-violation]
- [x] AC-62: WHEN the reviewer evaluates a real Edge Runtime import bug THEN it is classified as CRITICAL and the gate blocks [REQ: explicit-severity-rubric-in-review-prompt, scenario: reviewer-evaluates-a-real-security-issue]
- [x] AC-63: WHEN the classifier encounters an ambiguous finding with no explicit severity tag THEN it defaults to the LOWER tier per the rubric [REQ: classifier-rubric-matches-review-prompt, scenario: classifier-sees-a-review-text-with-unclear-severity-tags]
- [x] AC-64: WHEN the classifier encounters a reviewer-tagged CRITICAL that the rubric says is MEDIUM THEN it emits the finding with `severity=MEDIUM` AND records a `downgrades` entry with `from=CRITICAL, to=MEDIUM` AND `source=classifier_downgrade` [REQ: classifier-rubric-matches-review-prompt, scenario: classifier-sees-a-review-text-with-mismatched-severity]
- [x] AC-65: WHEN the review gate fails with mixed severities THEN the retry prompt groups findings into `## Must Fix`, `## Should Fix`, `## Nice to Have` sections with instructions on priority order [REQ: agents-fix-prompts-reflect-severity, scenario: retry-prompt-with-mixed-severities]
- [x] AC-66: WHEN the review gate fails with only CRITICAL findings THEN only the `## Must Fix` section is rendered in the retry prompt [REQ: agents-fix-prompts-reflect-severity, scenario: retry-prompt-with-only-critical]
- [x] AC-67: WHEN the classifier downgrades findings THEN the `<session_id>.verdict.json` sidecar includes a `downgrades` array with per-entry from/to/summary [REQ: severity-downgrade-audit-trail, scenario: downgrade-recorded-in-sidecar]

### supervisor-permanent-errors

- [x] AC-68: WHEN the orchestrator exits non-zero AND stderr contains `Error: Spec file not found:` THEN the supervisor halts immediately with `stop_reason: permanent_error:spec_not_found` without consuming a rapid-crash slot [REQ: supervisor-distinguishes-permanent-errors-from-transient-crashes, scenario: spec-file-not-found-on-first-start]
- [x] AC-69: WHEN the orchestrator exits non-zero AND stderr contains a Python `Traceback` header (no permanent-signal match) THEN the supervisor retries per the normal budget [REQ: supervisor-distinguishes-permanent-errors-from-transient-crashes, scenario: orchestrator-crashes-with-a-python-traceback-transient]
- [x] AC-70: WHEN the orchestrator exits with code 127 THEN the supervisor halts with `permanent_error:orchestrator_binary_missing` [REQ: supervisor-distinguishes-permanent-errors-from-transient-crashes, scenario: orchestrator-exits-with-code-127-binary-not-found]
- [x] AC-71: WHEN stderr does not match any entry in `PERMANENT_ERROR_SIGNALS` THEN `_classify_exit()` returns `None` and the retry path runs [REQ: permanent-error-catalog-in-anomaly-module, scenario: unknown-stderr-pattern]
- [x] AC-72: WHEN a developer adds a new entry to `PERMANENT_ERROR_SIGNALS` THEN the supervisor picks it up on the next start with no other code changes AND a corresponding unit test exists [REQ: permanent-error-catalog-in-anomaly-module, scenario: adding-a-new-permanent-error]
- [x] AC-73: WHEN the daemon halted with a permanent error THEN `/api/{project}/sentinel/status` response includes `permanent_error: {code, stderr_tail}` [REQ: manager-api-surfaces-permanent-errors-prominently, scenario: dashboard-shows-permanent-error-after-spec-typo]
- [x] AC-74: WHEN the daemon halted with a normal inbox_stop reason THEN the response does NOT include `permanent_error` [REQ: manager-api-surfaces-permanent-errors-prominently, scenario: dashboard-shows-normal-stopped-state-after-manual-halt]
- [x] AC-75: WHEN a unit test feeds `"Error: Spec file not found: docs/spec.md\n"` to `_classify_exit()` THEN the function returns `"spec_not_found"` [REQ: unit-test-coverage-for-each-permanent-error-signal, scenario: test-for-spec-not-found]
- [x] AC-76: WHEN a unit test feeds a Python traceback to `_classify_exit()` THEN the function returns `None` [REQ: unit-test-coverage-for-each-permanent-error-signal, scenario: test-for-transient-python-traceback]
