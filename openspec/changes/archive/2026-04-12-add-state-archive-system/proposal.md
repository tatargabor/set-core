# Proposal: State Archive System + Supervisor / Merge / Learnings Quality Fixes

## Why

Orchestration loses valuable debugging data because state.json fields (gate results, gate outputs, retry contexts, status transitions) are overwritten on every update, and worktree-local files (`.set/reflection.md`, `.set/activity.json`, `.claude/review-findings.md`) plus singleton files (`sentinel/findings.json`, `sentinel/status.json`, `spec-coverage-report.md`) are replaced or lost without history. The immediate user-visible pain: the web dashboard's Build/Test/E2E/Review gate tabs show only the last run for a change, even though `foundation-setup` went through 10 sessions with multiple retry cycles — users cannot inspect earlier failures or compare attempts.

**The minishop-run-20260412-0103 validation run exposed five additional production-blocking quality issues in the supervisor + merge + review learnings + review severity + permanent-error paths.** Each is a narrow, well-isolated bug with a concrete observation, a known root cause, and an already-drafted fix. They share state semantics with the archive system (both touch `update_change_field`, the supervisor status file, and the issue registry) so bundling them into one change avoids a second round-trip through the openspec workflow and keeps the state/status surface coherent:

1. **Supervisor re-fires triggers on steady state.** After the retry budget for `integration_failed` exhausted, the detector kept firing every 15s against the same `failed` status, writing a `skipped: retry_budget_exhausted` event each time. Observed 02:44 → 10:18, ~7.5h of event log spam. Fix: detectors fire on transitions only. See `supervisor-transition-triggers` capability.

2. **Issue ownership blocks merge queue without recovery.** Three ephemeral Claude triggers wrote findings, each created an `ISS-NNN` issue in state `diagnosed`. `merger.execute_merge_queue()` skipped the change on every poll via `_get_issue_owned_changes()`. The run was unblocked only by manually editing `.set/issues/registry.json`. Fix: auto-resolve issues on successful merge + diagnosed-state timeout visibility + manager API resolve endpoint. See `issue-merge-unblock` capability.

3. **Ralph loop never sees newly-written learnings.** `dispatcher._build_input_content()` writes `input.md` once at initial dispatch. Subsequent ralph iterations reuse the same file, so learnings persisted by earlier merged changes never reach a change that was already dispatched. Fix: regenerate `input.md` between ralph iterations when the learnings file's mtime is newer. See `ralph-learnings-injection` capability.

4. **Review severity calibration is too aggressive.** 18 CRITICAL findings across 46 total in the run, but only ~6 were genuine security/data-loss issues. The reviewer template has no severity rubric, so Opus defaults to flagging design-system violations as CRITICAL. Fix: explicit rubric in both the review prompt and the classifier prompt + retry context groups findings by severity. See `review-severity-calibration` capability.

5. **Supervisor retries permanent errors.** A spec-path typo in the first minishop start caused three back-to-back `Spec file not found` crashes before the rapid-crash budget exhausted and the daemon halted. Fix: pattern-match stderr against a `PERMANENT_ERROR_SIGNALS` catalog and halt immediately on match, with a visible error surfaced to the dashboard. See `supervisor-permanent-errors` capability.

All five fixes are drafted in their own spec files under `specs/`. They are additive — none modify existing archive/journal/harvest specs — and they land in the same commit cycle so a single deploy covers the entire quality improvement surface.

## What Changes

### Archive / Journal / Harvest (original scope)
- **ADD** a change journal system that hooks into `update_change_field()` and appends every overwrite of selected state.json fields (gate results/outputs/timings, retry context, status, current_step) to a per-change append-only JSONL file at `<orchestration_dir>/journals/<change-name>.jsonl`.
- **ADD** a general-purpose `archive_and_write()` helper under `lib/set_orch/archive.py` that snapshots any tracked file before overwriting, storing snapshots under `<orchestration_dir>/archives/<relative-path>/<ts>.<ext>` with optional `.meta.json` sidecars and optional rolling retention.
- **ADD** a post-merge worktree harvest step that copies `.set/reflection.md`, `.set/loop-state.json`, `.set/activity.json`, and `.claude/review-findings.md` from each merged worktree to `<orchestration_dir>/archives/worktrees/<change-name>/`, preserving them independent of worktree lifecycle.
- **ADD** a new backend endpoint `GET /api/{project}/changes/{name}/journal` that returns the raw journal entries plus a gate-grouped run-history view.
- **ADD** web dashboard support: rename the bottom-panel "Task" tab to "Session", and render per-run sub-tabs under each gate tab (Build/Test/E2E/Review/Smoke) driven by the journal API. Legacy changes without journals fall back to the current single-run view.
- **APPLY** `archive_and_write()` at three call sites: `sentinel/findings.py::_write()`, `sentinel/status.py::_write()` (with `max_archives=20` because frequent), and `engine.py` spec-coverage-report regeneration.

### Supervisor / Merge / Learnings Quality Fixes (bundled)
- **ADD** transition-based anomaly detection: `detect_integration_failed`, `detect_terminal_state`, and `detect_token_stall` fire only on status TRANSITIONS, tracked via a new `last_change_statuses: dict[str, str]` field on `SupervisorStatus`.
- **ADD** issue auto-resolve on change merge: `merge_change()` transitions all `affected_change` issues from `diagnosed` → `fixed` atomically, with full audit trail. Also adds a `diagnosed_at` timestamp + watchdog timeout visibility + `POST /api/{project}/issues/{id}/resolve` endpoint for manual escape.
- **ADD** ralph iteration input.md refresh: `dispatcher._maybe_refresh_input_md()` regenerates the agent's input file between iterations when `review-learnings.jsonl` has a newer mtime, so in-flight changes pick up learnings from changes that merged during their ralph loop.
- **ADD** explicit severity rubric to `render_review_prompt()` and `_build_classifier_prompt()` so CRITICAL is reserved for crash/leak/data-loss. Classifier gains a `downgrades` field in the sidecar when it lowers a finding's tag per the rubric. Retry context groups findings by `Must Fix / Should Fix / Nice to Have`.
- **ADD** permanent-error detection in `_restart_orchestrator()`: a `PERMANENT_ERROR_SIGNALS` catalog in `supervisor/anomaly.py` matches known deterministic failure patterns (spec not found, missing binary, import error) against stderr tail. On match, the daemon halts without consuming retry slots and surfaces the reason to the dashboard via `sentinel/status`.

## Capabilities

### New Capabilities
- `change-journal` — per-change append-only journal of state.json field overwrites, with read API.
- `file-archive` — generic archive-before-overwrite helper for tracked files, with rolling retention.
- `worktree-harvest` — post-merge copy of valuable worktree-local files to persistent archive.
- `gate-history-view` — web dashboard rendering of per-run gate history sub-tabs from the journal.
- `supervisor-transition-triggers` — supervisor anomaly detectors fire on status transitions, not steady state.
- `issue-merge-unblock` — issue registry auto-resolves on successful merge + timeout visibility + operator resolve API.
- `ralph-learnings-injection` — dispatcher refreshes `input.md` between ralph iterations when learnings update.
- `review-severity-calibration` — explicit severity rubric in review and classifier prompts with downgrade audit trail.
- `supervisor-permanent-errors` — pattern-match stderr against a catalog and halt immediately on deterministic failures.

### Modified Capabilities
None. The existing `log-archive` capability continues to cover `.claude/logs/*.log` archiving during worktree cleanup; this change adds complementary but distinct archive flows for journal data, generic files, and worktree artifacts. The new supervisor/merge/learnings capabilities are all additive.

## Impact

**Code affected — Archive / Journal / Harvest:**
- `lib/set_orch/state.py` — hook in `update_change_field()` (no schema change).
- `lib/set_orch/paths.py` — new path resolvers for journal/archive/harvest directories.
- `lib/set_orch/archive.py` — NEW module.
- `lib/set_orch/worktree_harvest.py` — NEW module.
- `lib/set_orch/merger.py` — `cleanup_worktree()` gains a non-blocking harvest call.
- `lib/set_orch/sentinel/findings.py`, `sentinel/status.py` — switch `_write()` to `archive_and_write()`.
- `lib/set_orch/engine.py` — spec-coverage-report regeneration uses `archive_and_write()`.
- `lib/set_orch/api/orchestration.py` — NEW `/changes/{name}/journal` endpoint.
- `web/src/lib/api.ts` — new `JournalEntry` + `getChangeJournal()` types and fetcher.
- `web/src/components/LogPanel.tsx` — Task → Session rename and gate sub-tab rendering.
- `web/tests/e2e/` — new Playwright test covering the gate history sub-tabs.

**Code affected — Supervisor / Merge / Learnings Quality Fixes:**
- `lib/set_orch/supervisor/anomaly.py` — add `last_change_statuses` to AnomalyContext + transition-check in `detect_integration_failed`, `detect_terminal_state`, `detect_token_stall`; add `PERMANENT_ERROR_SIGNALS` catalog + `_classify_exit()` helper.
- `lib/set_orch/supervisor/state.py` — add `last_change_statuses: dict[str, str]` field to `SupervisorStatus`.
- `lib/set_orch/supervisor/daemon.py` — read/write `last_change_statuses` via the existing `_build_anomaly_context`/`_scan_and_dispatch_anomalies` path; `_restart_orchestrator()` calls `_classify_exit()` and halts on permanent error; `_shutdown()` persists the `permanent_error` field.
- `lib/set_orch/merger.py` — `merge_change()` calls new `_auto_resolve_issues_for_change()` on successful merge.
- `lib/set_orch/issues/audit.py`, `issues/models.py` — add `diagnosed_at` timestamp + `auto_resolve_for_change()` helper.
- `lib/set_orch/engine.py` or a new `lib/set_orch/issues/watchdog.py` — periodic check for issues stuck in `diagnosed` past the timeout.
- `lib/set_orch/api/sentinel.py` or `api/issues.py` — new `POST /api/{project}/issues/{id}/resolve` endpoint.
- `lib/set_orch/api/_sentinel_orch.py` — `/sentinel/status` includes `permanent_error` field when applicable.
- `lib/set_orch/dispatcher.py` — `_maybe_refresh_input_md()` helper called between ralph iterations.
- `lib/set_orch/loop_state.py` — hook point to trigger the dispatcher refresh check.
- `lib/set_orch/templates.py::render_review_prompt` — add Severity Rubric section + retry context grouping.
- `lib/set_orch/llm_verdict.py::_build_classifier_prompt` — add condensed rubric + `downgrades` field in result.
- `lib/set_orch/gate_verdict.py::GateVerdict` — add `downgrades: list[dict]` field.
- `lib/set_orch/verifier.py::review_change` — pass rubric-aware prompt prefix on retry.
- `tests/unit/test_supervisor_anomaly.py` — transition tests for the 3 affected detectors + `_classify_exit()` tests for each `PERMANENT_ERROR_SIGNALS` entry.
- `tests/unit/test_issues_auto_resolve.py` — NEW test file for issue auto-resolve.
- `tests/unit/test_dispatcher_input_refresh.py` — NEW test file for input.md refresh between iterations.
- `tests/unit/test_verifier.py` — new cases for severity rubric downgrade.
- `web/src/pages/ProjectStatus.tsx` — render permanent-error banner when `sentinel/status` has the field.

**Data storage:**
- New directories under `<orchestration_dir>`: `journals/`, `archives/`, `archives/worktrees/`. Bounded per change (journal ~1–2 MB worst case after many retries), unbounded across changes (cleanup is out of scope; future `set-cleanup` command).

**Backward compatibility (explicit decision — see design.md Decision 10):**
- Full legacy fallback is a deliberate choice, not a side effect. Rejected alternatives: drop backward compat with a required migration; lazy bootstrap that writes a synthetic "Run 1" on first journal read.
- No state.json schema change; old state files are read unchanged.
- Changes without journals keep working; the LogPanel's legacy single-run rendering path is preserved for them and for new changes whose gates have not yet run.
- No migration of existing historical data — the journal starts empty and fills going forward.
- Implementation lands BEFORE the next E2E run, so no live run is disrupted.

**Performance:**
- Journal writes happen outside the state lock on a hot path (`update_change_field` is called hundreds of times per run); each write is a short appended JSONL line. Expected overhead <1 ms per call.
- `archive_and_write()` adds one file copy per affected write; these sites are low-frequency (sentinel updates, coverage regeneration).
- Harvest runs once per merge, non-blocking.

**Risks:**
- Journal file growth on pathological retry loops — bounded because gate outputs are already truncated in `gate_runner.py` (2 KB default, 32 KB for E2E).
- Archive directory growth unmanaged — accepted for first pass; documented as a follow-up for `set-cleanup`.
