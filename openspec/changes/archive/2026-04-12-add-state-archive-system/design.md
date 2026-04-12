# Design: State Archive System

## Context

set-core stores orchestration state in three layers:
1. **state.json** — the single source of truth for current state per change. `update_change_field()` in `lib/set_orch/state.py` is the only write entry point and overwrites fields in place.
2. **events.jsonl** — an append-only event bus for observability. Present but optional (`event_bus` parameter is frequently `None`), and does NOT store gate outputs.
3. **Per-worktree files** — `.set/reflection.md`, `.set/loop-state.json`, `.set/activity.json`, `.claude/review-findings.md`. These live inside the worktree and can disappear when the worktree is removed.

The user's concrete pain point: the web dashboard's gate tabs (Build/Test/E2E/Review) show only the last value of `build_output`, `e2e_output`, etc., because state.json overwrites these on every retry. For `foundation-setup` with 10 sessions and multiple retry cycles, the history is gone.

Earlier exploration identified three separate data-loss categories: (a) state.json field overwrites, (b) singleton file overwrites (sentinel findings/status, coverage report), and (c) worktree-local files with lifecycle risk. Each category needs a different mechanism because they have different write patterns and central-hook availability.

### Runtime path topology — CRITICAL

set-core has two runtime layouts that coexist on the same machine:

**Normal install:**
```
~/.local/share/set-core/runtime/<project>/
├── orchestration/
│   ├── state.json
│   ├── events.jsonl
│   ├── report.html
│   └── plans/
├── sentinel/
│   ├── findings.json
│   ├── status.json
│   └── events.jsonl
└── logs/
```

**E2E runner layout (`e2e-runs/`):**
```
~/.local/share/set-core/e2e-runs/<run-name>/      ← state + worktrees
├── orchestration-state.json                      ← note: flat, not under orchestration/
├── .worktrees/
└── (actual project source files)

~/.local/share/set-core/runtime/<run-name>/       ← observability
├── orchestration/
│   ├── events.jsonl
│   ├── report.html
│   └── plans/
├── sentinel/
└── logs/
```

The split is deliberate: e2e runs keep the project workspace (where git operations happen) separate from the observability artifacts. `SetRuntime()` always points at the `runtime/` path, but `state.json` is at a different location in the e2e case.

**Implication for this change:** code that runs on the `update_change_field()` hot path must NOT call `SetRuntime()`, because `SetRuntime.__init__` invokes `git rev-parse --show-toplevel` via subprocess. Subprocess in the hot path is unacceptable (it is called hundreds of times per minute during active orchestration). All journal path resolution must be derived directly from the `state_file` argument that is already passed into `update_change_field()`.

**Currently running:** `minishop-run-20260412-0103`. Its state file lives at `e2e-runs/minishop-run-20260412-0103/orchestration-state.json` and `orchestration.log` shows continuous `update_change_field` activity every few seconds. This run must not be disrupted by the deploy.

## Goals / Non-Goals

**Goals:**
- Preserve gate result, gate output, gate timing, and retry history per change so users can inspect prior attempts in the web dashboard.
- Provide a reusable archive-before-overwrite helper for singleton files, starting with sentinel/findings, sentinel/status, and spec-coverage-report.
- Harvest valuable worktree-local files after successful merges so they survive even if the worktree is later removed.
- Maintain backward compatibility: no state.json schema change, legacy changes continue to work, journal starts empty on existing projects.
- Keep the implementation surface area minimal and all changes non-blocking on the hot path.

**Non-Goals:**
- Automatic cleanup/retention across all archives (only per-call-site `max_archives` where appropriate).
- Migration of existing historical data (journals start empty).
- A generic filesystem watcher that automatically archives every write.
- Archiving cache files (`cache/designs/`, `cache/codemaps/`) — these are re-derivable.
- Harvesting while the worktree is live — only on merge completion.
- New UI beyond gate history sub-tabs (sentinel findings history, coverage trend view, etc. come later).

## Decisions

### Decision 1: Hook `update_change_field()` rather than per-caller instrumentation
Every state.json write already funnels through `update_change_field()` in `state.py` (~80 call sites across `verifier.py`, `merger.py`, `dispatcher.py`, `gate_runner.py`, etc.). Hooking the central write function means zero caller changes — adding a field to `_JOURNALED_FIELDS` is the only action needed to enable journaling for a new field.

**Alternatives considered:**
- **Touch each call site** — rejected because ~80 sites would need changes and adding a new journaled field later would repeat the work.
- **Post-hoc log scraping from events.jsonl** — rejected because (a) event_bus is optional and sometimes `None`, (b) events never carry gate outputs, and (c) event-to-session association is fragile.
- **Gate result history inside a Change dataclass list field** (the `review_history` extras pattern) — viable but mixes "current state" and "history" in state.json; the append-only journal file keeps them cleanly separated and avoids inflating the hot-path state read.

### Decision 2: Journal writes happen INSIDE the state lock, matching the existing event bus pattern
`update_change_field()` already emits `STATE_CHANGE` and `TOKENS` events via `event_bus.emit()` from INSIDE the `with locked_state(path) as state:` block (see `state.py` lines 501-531). The event bus writes those events to `events.jsonl`, which is file I/O performed under the state lock. Journal append is the same kind of operation — a short, append-only file write — so it belongs in the same place for three reasons:

1. **Atomicity:** state update and journal append succeed or fail together. There is no window between lock release and journal write where a crash can drop an entry.
2. **Consistency with existing code:** one established pattern for "after mutating state, record observability data". Diverging would add a second pattern with no benefit.
3. **No cross-change contention:** journal files are per-change, so two parallel changes never contend on the same journal file. Within a single change, writes are naturally serialized (one process is actively updating a given change at a time).

**Alternatives considered:**
- **Write journal after lock release** — initially proposed, but rejected on reflection. Losing exactly one journal entry on a crash between release and append is not a catastrophic bug, but it is an avoidable class of bug. The contention argument that motivated this design does not hold because journal files are per-change.
- **Let the event bus carry journal data** — rejected because event_bus is optional (frequently `None`), is project-wide (cross-change filtering required), and does not carry gate outputs today. The journal is a separate, required, per-change mechanism.

**Trade-off:** each `update_change_field()` call with a journaled field adds one extra short file append under the state lock. Measured against existing event bus writes that already happen there, the overhead is comparable and bounded.

### Decision 3: Per-change journal files next to state.json (not in SetRuntime())
`<state_file_parent>/journals/<change-name>.jsonl` gives each change its own file, derived purely from the `state_file` argument. No `SetRuntime()` call, no subprocess, no paths.py import.

**Path resolution rule** — for both normal and e2e layouts:
```python
journal_dir = os.path.join(os.path.dirname(state_file), "journals")
journal_file = os.path.join(journal_dir, f"{change_name}.jsonl")
```

**Concrete cases:**
- Normal: `state.json` at `runtime/<project>/orchestration/state.json` → journals at `runtime/<project>/orchestration/journals/` (sibling to events.jsonl).
- E2E: `orchestration-state.json` at `e2e-runs/<run>/orchestration-state.json` → journals at `e2e-runs/<run>/journals/` (sibling to state file, NOT next to events.jsonl which lives in the runtime dir).

**Alternatives considered:**
- **`SetRuntime()` with subprocess lookup** — rejected because it runs git on every `update_change_field` call. Even with caching, the first call per state file would block the hot path. events.py can afford this because it's called once at module init; `update_change_field` is called hundreds of times per change.
- **Late import with cache** — workable but adds complexity for a feature where "next to state.json" is already correct.
- **Project-wide journal.jsonl** — rejected; API would scan every line to filter per change, and unbounded growth across all changes.
- **Embedded in state.json extras (like `review_history`)** — rejected; state.json is read on every engine tick and would grow with history (performance + lock contention).

**Trade-off:** in the e2e layout, journals end up next to the state file rather than next to events.jsonl. This means the journal files are not in the observability tree. Acceptable because (a) the web API receives the project path at request time and can derive `journal_dir` from the state file the same way state.py does, (b) e2e runners already archive the entire e2e-runs workspace for postmortem, so journals survive there too.

### Decision 4: `archive_and_write()` is opt-in at call sites, not a filesystem hook
Only three current write sites warrant archiving: sentinel findings (restart-resilience), sentinel status (history), and coverage report (trend). Other overwrites (cache files, transient worktree files) are either re-derivable or irrelevant. Requiring callers to opt in keeps the abstraction honest — the archive directory doesn't fill with junk.

**Alternatives considered:**
- **Filesystem watcher on orchestration_dir** — rejected as overkill; too many false positives (lock files, temp files), hard to debug.
- **Decorator on all write functions** — rejected because `open(path, 'w')` and `json.dump()` callers are spread widely and don't share a common entry point like `update_change_field()` does.

### Decision 5: Post-merge harvest in `cleanup_worktree()` rather than a separate stage
`cleanup_worktree()` already runs after every successful merge and already archives `.claude/logs/*.log` and test artifacts. Adding harvest there reuses existing code flow and timing. The harvest runs regardless of retention policy (so even `retention=keep` changes get harvested), because the point is to have the data in a stable location independent of worktree fate.

**Trade-off:** Harvest runs even when unnecessary (e.g., the worktree is explicitly preserved). Acceptable — a fast file copy is cheap, and the alternative (trying to predict future worktree removal) is brittle.

### Decision 6: Collision handling for worktree harvest destination — timestamp suffix
Change names are normally unique within a project, so `archives/worktrees/<change-name>/` is deterministic. But nothing in the type system prevents reuse (especially in E2E runners that recycle names after cleanup). On collision we append `.YYYYMMDDTHHMMSSZ` to the directory and log a WARNING, giving defense-in-depth without requiring strict uniqueness.

### Decision 7: Non-blocking everywhere
Journal failure, archive failure, harvest failure — all three log WARNING and continue. None of them affect state correctness or merge success. The archive system is observational; state.json remains the source of truth.

### Decision 8: Frontend — render sub-tabs inline, not as a separate component tree
The existing `LogPanel.tsx` has a flat sub-tab array (`Task | Build | Test | E2E | Review`). Adding a second tier under each gate tab is a state addition (`activeSubTab` + `activeRunIndex`) plus a conditional render. This keeps the diff small and the UX additive — users who ignore the sub-tabs see the latest run, same as today.

**Alternatives considered:**
- **Full component restructure** — rejected; overkill for a two-tier tab bar and would require rewiring auto-expand/auto-follow logic.
- **Dedicated gate-history page** — rejected; users want to scan gate history inline with the rest of the change detail view, not navigate away.

### Decision 9: Backend computes the `grouped` view
The API returns both `entries` (raw) and `grouped` (gate-run pairs) so the frontend doesn't need to reimplement pairing logic. The backend pairs entries by matching `gate_*_ms`/`*_result`/`*_output` writes that share a timestamp (or fall within a small window — the three writes happen consecutively in `gate_runner.py` lines 327-332).

**Alternatives considered:**
- **Frontend does grouping** — rejected because it duplicates Python logic in TypeScript and requires understanding the gate_runner write order in the UI layer.
- **Backend returns only grouped** — rejected because raw entries have debug value (timeline view, status transitions) that the frontend may want later.

### Decision 11: Supervisor transition tracking lives in `SupervisorStatus`, not in an ephemeral dict
The supervisor needs to know "what was this change's status last time I saw it" to decide whether a trigger condition represents a fresh transition or a steady state. That state must survive daemon restart — if the supervisor is killed while a change is in `failed` and the persisted history is lost, the new daemon would re-fire the trigger as if the failure just happened.

**Chosen approach:** add `last_change_statuses: dict[str, str]` (and `last_orch_status: str`, `crossed_token_stall_thresholds: set[str]`) to the existing `SupervisorStatus` dataclass in `lib/set_orch/supervisor/state.py`. Persisted via the existing `write_status()` / `read_status()` pair. Initialized empty on a fresh daemon, populated at the end of every `_build_anomaly_context` cycle from the observed state.

**Alternatives considered:**
- **In-memory dict on the daemon instance** — rejected because daemon restart is frequent (every code update, every manager restart, every crash recovery) and losing the history every time would defeat the purpose. The minishop-run-20260412-0103 incident happened precisely because the restart caused a fresh scan that saw `failed` as "new".
- **Derive transition from the orchestration events.jsonl** — rejected because the events log is unbounded and growing, and each detector would need its own cursor. The `last_change_statuses` dict is bounded by the number of changes (typically <20) and fits naturally with the existing status persistence.
- **Hash the whole state and skip triggers on identical hash** — rejected because it doesn't distinguish "same change still failing" (skip) from "different change just failed" (fire), and a single-change run's state changes tokens/heartbeats constantly so the hash would flip every poll anyway.

**Trade-off:** `status.json` grows by a few hundred bytes per change. Negligible. The status file is rewritten every poll already.

### Decision 12: Issue auto-resolve anchored on `merge_change()` completion, not MERGE_SUCCESS event
Issues in state `diagnosed` block the merge queue (`_get_issue_owned_changes` reads them and returns their change names). The simplest fix — transition issues to `fixed` as a consequence of a successful merge — needs an anchor point that is:
1. Guaranteed to run exactly once per merge
2. Runs AFTER the merge is committed (so partial merges don't mark issues fixed)
3. Runs even if the event_bus is missing or misconfigured

**Chosen approach:** call `auto_resolve_for_change()` inside `merger.merge_change()` right after the `status=merged` state update at line ~691. This is the innermost "merge is final" site; by the time we reach it, `set-merge` has returned 0, the post-merge verification passed, the status is committed. Wrapping the call in try/except ensures registry update failures don't rollback the merge.

**Alternatives considered:**
- **Subscribe to `MERGE_SUCCESS` event via event_bus** — rejected because event_bus is optional (`None` in many execution paths) and the resolver is best-effort already. Anchoring at the code site eliminates the event-vs-action ordering race entirely.
- **Run resolver in a background watchdog loop** — rejected because the latency matters: the very next merge-queue drain poll (15 seconds later) would see the stale issue and skip the NEXT change, too.
- **Keep manual-only resolution with a better error message** — rejected because the whole point of the supervisor is that it doesn't need human intervention to recover from routine state.

**Trade-off:** auto-resolve assumes that if the merge passed all gates, any findings on the change are either fixed or acceptable. This is the same trust model the merge queue already uses (the merged change is the new main). A false-positive auto-resolve (issue logged against wrong change) would be rare and recoverable by operator action.

### Decision 13: Ralph `input.md` refresh keyed on learnings-file mtime, not explicit version bumps
The dispatcher writes `input.md` once at initial dispatch and then the ralph loop reuses it. Post-merge sibling learnings land in `review-learnings.jsonl` but never reach the in-flight agent. The refresh trigger must be cheap (checked every iteration) and must not regenerate the file when nothing has changed.

**Chosen approach:** on every iteration-end hook, compare `os.stat(learnings_file).st_mtime` to `os.stat(input_md).st_mtime`. If learnings is newer, regenerate. The check is O(2 stat syscalls), well under 1 ms.

**Alternatives considered:**
- **Content hash comparison** — rejected as overkill. Learnings file only grows (append-only with periodic semantic dedup), so mtime is a perfect proxy.
- **Explicit version field in the learnings JSONL** — rejected because it requires writing a new format and migrating existing files. mtime is schema-free.
- **Re-read learnings inside the running agent's Python environment (no file write)** — rejected because the agent is a Claude subprocess, not a Python process we control. The only communication channel is the file.

**Trade-off:** if the operator manually touches the learnings file (e.g., `touch review-learnings.jsonl` to force a refresh), the feature triggers unnecessarily. Acceptable — the refresh cost is ~50 ms and the outcome is still correct (fresh input.md with current learnings).

### Decision 14: Severity rubric as a text insert, not a structured schema
The review prompt and classifier prompt both need the same tiering. The tiering itself is ~20 lines of text with examples. It's tempting to put the rubric in a shared YAML/JSON file and template it into both prompts, but that adds indirection without solving a real problem.

**Chosen approach:** duplicate the rubric text in both `render_review_prompt()` and `_build_classifier_prompt()`. Keep the authoritative copy in `specs/review-severity-calibration/spec.md` (referenced by the task list) so both code sites can be audited against the same source of truth.

**Alternatives considered:**
- **Shared YAML file + loader** — rejected because the two prompts have slightly different framing (reviewer gets full examples, classifier gets condensed form) and templating would add conditional blocks that obscure both.
- **Inject as a runtime directive from orchestration.yaml** — rejected because severity rubric is a code-level decision, not a per-project tunable. Promoting it to config would invite per-project drift.

**Trade-off:** if the rubric ever changes, two files must be updated. The spec serves as the reminder.

### Decision 15: Permanent-error detection is stderr-pattern based, not exit-code based
The supervisor needs to distinguish "this crash was caused by a known deterministic failure" from "this crash might recover on retry". Exit codes alone are insufficient: Python always exits 1 on unhandled exceptions, and the orchestrator catches most exceptions and exits 1 anyway.

**Chosen approach:** maintain a catalog of stderr substrings in `supervisor/anomaly.py::PERMANENT_ERROR_SIGNALS`. Match the last ~2 KB of orchestrator stderr against the catalog on each crash. Match returns the reason code; no match means retry.

**Alternatives considered:**
- **Exit code catalog** — partial coverage only (127 = binary missing is useful, but most permanent errors still exit 1). Would need stderr matching anyway.
- **Custom exit codes from set-orchestrate** — rejected because it requires coordinated changes across every orchestrator entry point AND doesn't help for errors that happen before the orchestrator's own error handler can run.
- **Parse the orchestrator's structured log output (JSON)** — rejected because orchestration.log is plain text and the stderr stream is where the early-exit errors land anyway.

**Trade-off:** pattern matching on stderr is fragile when error messages change. Mitigated by: (a) the patterns are substrings of English error messages that haven't changed in 2 years, (b) each entry has a unit test, (c) an unknown stderr = fall through to retry, which is the safe default.

### Decision 10: Backward compatibility — full legacy fallback, no migration
Existing projects have state.json files with gate result/output fields populated but no journal. The LogPanel must keep working for them.

**Chosen approach:** the journal starts empty on existing changes. The LogPanel reads journal data when present; when absent (empty `grouped` object), it falls back to reading `build_result`/`build_output`/`gate_build_ms` (and equivalents for the other gates) directly from `ChangeInfo`, exactly as it works today. No state.json schema change, no migration step, no dev-only bootstrap.

**Alternatives considered:**
- **Drop backward compat, require migration** — rejected because a live E2E run can be in progress (e.g., `minishop-run-20260412-0103`) and any deploy that breaks in-flight changes is unacceptable. Implementation will happen before the next E2E run anyway, so the window where legacy state.json files coexist with new code is real and must not break them.
- **Bootstrap lazy migration: on first journal read, back-fill a single synthetic entry from ChangeInfo so every change has at least Run 1** — rejected because it writes from a GET endpoint (side effect in a read path) and presents a fake "Run 1" that is really just the current snapshot, giving the user a misleading history view with no actual retries visible.

**Trade-off:** the LogPanel keeps two rendering paths forever (journal-driven sub-tabs vs legacy single-run). This is cheap because the legacy path is a small conditional and is exactly what the panel already does today. The second path is NOT dead code — it also serves the "gate has no runs yet" state for new changes, so removing it would require another special case anyway.

## Risks / Trade-offs

**[Risk]** Journal file growth on pathological retry loops → **Mitigation:** gate outputs are already truncated at source (`gate_runner.py::_truncate_gate_output`, 2 KB default, 32 KB for E2E). Worst case: 20 retries × 5 gates × 32 KB ≈ 3.2 MB per change. Acceptable.

**[Risk]** Journal append race between concurrent processes → **Mitigation:** `O_APPEND` mode guarantees atomic writes for lines up to `PIPE_BUF` (typically 4 KB). For larger lines (E2E output), wrap the append in an advisory `flock()` on the journal file. The lock scope is local to the journal file, not the state lock.

**[Risk]** Archive disk usage grows unbounded → **Mitigation:** per-site `max_archives` where frequency warrants (status updates). For findings/coverage report, low frequency means unbounded is tolerable. Global cleanup deferred to a future `set-cleanup` CLI.

**[Risk]** Harvest destination collision corrupts prior harvest → **Mitigation:** detect existing destination and use timestamped fallback name. Never overwrite an existing harvest directory.

**[Risk]** Frontend sub-tabs break existing auto-expand / auto-follow behavior → **Mitigation:** keep the outer `activeSubTab` state and selection logic unchanged; nest `activeRunIndex` state inside gate tabs only. Default to latest run preserves the "show the current state" feel.

**[Risk]** Journal endpoint returns stale data if consumed during an active run → **Mitigation:** journal is append-only, so the client always sees a consistent prefix. The UI can re-fetch on interval (like the existing session polling).

**[Risk]** Backward compatibility regression for legacy changes → **Mitigation:** journal fetcher treats empty/missing as "no history"; frontend falls back to the current single-run view. Explicitly covered by a Playwright scenario.

## Migration Plan — Safe Deploy Against a Live Run

**Preconditions:**
- Run `minishop-run-20260412-0103` is active and writing state every few seconds.
- set-web.service hosts the orchestrator and manager API (single systemd user service).
- Agent claude subprocesses run under set-web.service.
- The user wants the change deployed BEFORE the next run, but not DURING the current one.

### Phase 0 — Baseline capture (can run now, does not touch live state)

0.1 Verify this document's assumptions still match the running process:
   ```
   systemctl --user status set-web.service
   ls -la /home/tg/.local/share/set-core/e2e-runs/minishop-run-20260412-0103/orchestration-state.json
   tail -n 20 /home/tg/.local/share/set-core/runtime/minishop-run-20260412-0103/logs/orchestration.log
   ```
0.2 Snapshot the current git HEAD: `git rev-parse HEAD` — this is the rollback target.
0.3 Confirm the orchestrator is actively updating state (log lines in the last 60 seconds). If not active, the plan becomes easier — there's no live run to protect.

### Phase 1 — File-level code changes (zero runtime impact)

File edits do not take effect until set-web.service restarts. The running orchestrator holds all library code in memory, so editing `.py` files on disk is safe as long as no restart happens.

1.1 **state.py hook** (the single highest-risk change):
   - Add `_JOURNALED_FIELDS` frozenset at module level.
   - Add `_append_journal(state_file, change_name, field, old, new)` helper. Uses only stdlib (`json`, `os`, `datetime`, `fcntl`, `pathlib`). Broad try/except at outermost scope; never raises.
   - Path derivation: `os.path.join(os.path.dirname(state_file), "journals", f"{change_name}.jsonl")`. No SetRuntime import.
   - Insert the hook call INSIDE `locked_state` block, after the `logger.info("State update: ...")` line (state.py ~L499), gated by `field_name in _JOURNALED_FIELDS and value != old_value`.
   - The hook is wrapped in its own try/except that catches `BaseException` (not just `Exception`) to ensure even weird failure modes like `KeyboardInterrupt` inside the journal append cannot escape.

1.2 **Create `lib/set_orch/archive.py`** — new file, no existing imports reference it yet, so it cannot break anything.

1.3 **Create `lib/set_orch/worktree_harvest.py`** — same, new file, no impact until called.

1.4 **Migrate archive call sites** one at a time:
   - `sentinel/findings.py::_write()` — replace the direct write with `archive_and_write()`, but keep the old logic as a `_legacy_write_direct()` fallback behind a try/except. On failure, log WARNING and call the fallback so findings are never lost.
   - `sentinel/status.py::_write()` — same pattern.
   - `engine.py` coverage report write — same pattern.

1.5 **merger.py harvest hook** — add `harvest_worktree()` call inside `cleanup_worktree()` wrapped in try/except. Non-blocking so the merge always completes.

1.6 **api/orchestration.py journal endpoint** — new route, additive. Cannot break existing endpoints.

1.7 **Frontend (web/)** — web/src/lib/api.ts and web/src/components/LogPanel.tsx + Playwright test. These are rebuilt by `pnpm build` and served by set-web after next restart. Editing them on disk has no runtime impact.

**At the end of Phase 1:** every file on disk contains the new code, nothing is running it yet, the current run continues on the old in-memory code.

### Phase 2 — Isolated unit tests (no live state touched)

2.1 `pytest tests/unit/test_state_journal.py` — tests use `tempfile.TemporaryDirectory` and synthetic state files. They MUST NOT read or write any file under `~/.local/share/set-core/runtime/` or `~/.local/share/set-core/e2e-runs/`.

2.2 `pytest tests/unit/test_archive.py` — same, temp dirs only.

2.3 `pytest tests/unit/test_worktree_harvest.py` — same.

2.4 `pytest lib/set_orch/tests/` — run the existing state.py unit tests to verify the hook did not break anything.

2.5 Smoke-import test: `python -c "import lib.set_orch.state; import lib.set_orch.archive; import lib.set_orch.worktree_harvest; import lib.set_orch.merger"` — catches import errors and syntax errors.

2.6 `cd web && pnpm build` — build the frontend. Fails fast on TypeScript errors, does not touch the dashboard running in the browser.

**Gate:** all tests must be green before moving to Phase 3. If ANY test fails, stop and fix before proceeding.

### Phase 3 — Wait for the current run to finish or pause

3.1 Monitor `orchestration.log` until the current run reaches a terminal state (all changes merged or the user pauses the run). Do NOT restart set-web while the log shows active state updates.

3.2 Alternatively: the user explicitly stops the current run via the dashboard. Confirm via dashboard that no change has `status: running` or `status: verifying`.

3.3 Capture a final snapshot of the current state.json for postmortem:
   ```
   cp /home/tg/.local/share/set-core/e2e-runs/minishop-run-20260412-0103/orchestration-state.json /tmp/pre-deploy-minishop-state.json
   ```

### Phase 4 — Deploy (service restart)

4.1 Commit the code changes on a branch, NOT to main yet (rollback via checkout if needed). Branch name: `add-state-archive-system`.

4.2 Restart set-web: `systemctl --user restart set-web`. Wait 5 seconds, then check `systemctl --user status set-web` — expect `active (running)` and no errors in the journal: `journalctl --user -u set-web -n 50`.

4.3 Verify the new endpoint responds: `curl http://localhost:7400/api/minishop-run-20260412-0103/changes/<change>/journal` → expect 404 (change not in state) or 200 with empty `{entries: [], grouped: {}}`. Either is success (endpoint is wired up).

4.4 Verify the hot-path import of `_append_journal` works — there is no ImportError in the log. If there is, the orchestrator can no longer update state and we must roll back immediately (Phase 6).

### Phase 5 — Verification with a fresh run

5.1 Start a NEW run using the existing runner: `./tests/e2e/runners/run-micro-web.sh` (or whichever is planned).

5.2 After the first gate runs, check that the journal file has been created:
   ```
   ls -la /home/tg/.local/share/set-core/e2e-runs/<new-run>/journals/
   cat /home/tg/.local/share/set-core/e2e-runs/<new-run>/journals/<first-change>.jsonl | head -5
   ```
   Expect at least one line with `status` or `current_step` transitions.

5.3 Open the dashboard, navigate to the running change, and verify:
   - The "Session" tab label is present (replaced "Task").
   - Clicking a gate tab (Build/Test/E2E/Review) with at least one run shows the new sub-tab row with a single `Run 1` button.
   - After a second run of the same gate (retry), a second sub-tab appears and clicking it shows the older output.
   - For changes with no journal yet (pending), the gate tabs fall back to the legacy view (today's behavior).

5.4 Check that `sentinel/findings.json` and `sentinel/status.json` archives appear under `<runtime>/sentinel/archives/` after the sentinel has written (first heartbeat + first findings update).

5.5 After the first successful merge in this run, check that `<runtime>/orchestration/archives/worktrees/<change-name>/` contains `reflection.md`, `loop-state.json`, `activity.json`, `review-findings.md` (whichever existed in the worktree), plus `.harvest-meta.json`.

### Phase 6 — Rollback procedure (if any verification fails)

Rollback is designed to be a single-command restore because all changes are additive.

6.1 **Fast rollback** (code bug, import error):
   ```
   git checkout <baseline-commit-from-phase-0.2> -- lib/ web/
   systemctl --user restart set-web
   ```
   The data on disk (journal files, archive snapshots, harvest dirs) is harmless and can be left in place or deleted later.

6.2 **Partial rollback** (one subsystem broken, others fine):
   - Only journal broken: remove `_append_journal` call from state.py (5 lines), restart set-web.
   - Only harvest broken: remove the `harvest_worktree()` call from merger.py (3 lines), restart.
   - Only archive_and_write broken: `git checkout` the three migrated files (`sentinel/findings.py`, `sentinel/status.py`, `engine.py`), restart.
   - Only frontend broken: `git checkout web/`, `cd web && pnpm build`, restart set-web.

6.3 **Data cleanup (only if requested)**: the journal/archive/harvest files can be deleted with `rm -rf` — they're not referenced by any runtime code.

### Order of operations — do NOT deviate

**DO:**
1. Edit files (Phase 1) while the run is active — safe, no runtime impact.
2. Run unit tests (Phase 2) in isolation — no live state touched.
3. Wait for the current run to finish (Phase 3) — no restart yet.
4. Commit to branch, restart, verify with new run (Phase 4-5).

**DO NOT:**
- Restart set-web while `minishop-run-20260412-0103` is actively writing state.
- Run integration tests against live runtime directories.
- Commit to main before Phase 5 has verified the new run works.
- Touch any file under `~/.local/share/set-core/runtime/minishop-run-20260412-0103/` or `~/.local/share/set-core/e2e-runs/minishop-run-20260412-0103/` during Phases 1-3.

## Open Questions

None blocking. A few follow-ups for a later iteration:
- A `set-cleanup` CLI command for pruning old journals and archives by age or count.
- A timeline visualization in the dashboard that reads raw journal entries to show status transitions, retries, and gate attempts on a single axis.
- A CLI `set-journal <change>` for human-readable printing.
- Extending the archive helper to additional call sites (e.g., `.set/reflection.md` inside a running worktree, if we decide per-iteration reflection history is valuable).
