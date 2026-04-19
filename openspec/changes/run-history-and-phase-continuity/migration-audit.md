# Migration Audit — Hardcoded Orchestration Paths → `LineagePaths`

Every call site that references an orchestration path is listed here with a migration checkbox. The `verify` gate for this change refuses to archive while any `[ ]` box remains unchecked in the **Code files** section (Python + Bash + TS + YAML). Documentation references are captured separately and are non-blocking for archiving — they are updated in a final docs sweep.

Audit methodology: ripgrep across the repo for 18 path patterns, de-duplicated by file. Excludes `.git/`, `node_modules/`, `__pycache__/`, `.next/`, `dist/`, `.venv/`, `.pytest_cache/`, `openspec/changes/archive/`, runtime project data under `~/.local/share/set-core/e2e-runs/`, and this change's own spec files.

Totals (baseline at audit time):
- Python: 77 files
- Bash/Shell: 28 files
- YAML: 2 files
- Markdown/Docs: 290 files (non-blocking)
- **Unique code files: 107** (blocking)

Legend for each row: `[ ]` = not migrated · `[x]` = migrated (uses `LineagePaths`) · `[~]` = N/A (read-only constant, no runtime resolution) · `[/]` = removed (file deleted or hardcoded string removed entirely).

---

## Phase 1 — Cross-cutting host: `LineagePaths` in `lib/set_orch/paths.py`

- [x] `lib/set_orch/paths.py` — add `LineagePaths` class; extend `SetRuntime` or wrap it. Support `lineage_id` parameter. Expose project-level + worktree-level path properties. Keep legacy `SetRuntime` unchanged for runtime-shared paths under `~/.local/share/set-core/`.

---

## Phase 2 — Python production (34 files)

### 2.a — Core engine & orchestration (READ + WRITE, highest risk)

- [x] `lib/set_orch/engine.py` — state WRITE, plan WRITE, archive WRITE, coverage WRITE, digest_dir reads (13 refs)
- [x] `lib/set_orch/dispatcher.py` — manifest WRITE, directives READ, review-findings references
- [x] `lib/set_orch/planner.py` — plan WRITE, domains WRITE, digest_dir reads (multiple sites)
- [x] `lib/set_orch/merger.py` — manifest READ, config READ, state READ, artifacts dir (10 refs)
- [ ] `lib/set_orch/verifier.py` — manifest WRITE, coverage consume
- [x] `lib/set_orch/recovery.py` — state READ
- [x] `lib/set_orch/config.py` — config.yaml READ, specs dir fallback
- [ ] `lib/set_orch/digest.py` — `DIGEST_DIR` constant → route through resolver
- [ ] `lib/set_orch/events.py` — events append sites
- [ ] `lib/set_orch/reporter.py` — state consume, merged_files resolution
- [ ] `lib/set_orch/auditor.py` — state READ
- [x] `lib/set_orch/notifications.py` — state READ
- [x] `lib/set_orch/cross_change.py` — state READ
- [x] `lib/set_orch/loop_prompt.py` — reflection READ
- [ ] `lib/set_orch/loop_state.py` — review-learnings path reference
- [x] `lib/set_orch/cli.py` — default path args (11 refs)
- [x] `lib/set_orch/cli_entry.py` — serve-time path wiring (verify no hardcoded)

### 2.b — Supervisor / sentinel (6 files)

- [ ] `lib/set_orch/supervisor/daemon.py` — events READ, state READ (13 refs)
- [ ] `lib/set_orch/supervisor/state.py` — status.json path
- [x] `lib/set_orch/supervisor/triggers.py` — state consume
- [x] `lib/set_orch/supervisor/canary.py` — state consume
- [ ] `lib/set_orch/supervisor/service.py` — spec-path write into status
- [x] `lib/set_orch/sentinel/status.py` — status.json writes via archive_and_write

### 2.c — API layer (8 files)

- [x] `lib/set_orch/api/orchestration.py` — events READ (dual-location fallback), state READ, archive merge
- [ ] `lib/set_orch/api/helpers.py` — state_path, log_path, archive path already partly centralised; extend with lineage-aware resolvers
- [ ] `lib/set_orch/api/activity.py` — events + rotated files enumeration
- [x] `lib/set_orch/api/activity_detail.py` — activity-detail-v2-*.jsonl path
- [x] `lib/set_orch/api/sessions.py` — session file discovery (partly worktree-based — confirm)
- [ ] `lib/set_orch/api/actions.py` — config.yaml, spec path handling
- [ ] `lib/set_orch/api/sentinel.py` — spec-path handling on start
- [x] `lib/set_orch/api/lifecycle.py` — IssueRegistry(project_path) — confirm path
- [x] `lib/set_orch/api/media.py` — artifact scan
- [ ] `lib/set_orch/api/_sentinel_orch.py` — sentinel events path

### 2.d — Issues subsystem (3 files)

- [x] `lib/set_orch/issues/registry.py` — `.set/issues/registry.json` path
- [ ] `lib/set_orch/issues/watchdog.py` — registry path
- [ ] `lib/set_orch/issues/manager.py` — registry consume

### 2.e — Manager / profile / misc (5 files)

- [x] `lib/set_orch/manager/service.py` — IssueRegistry + state access
- [x] `lib/set_orch/profile_loader.py` — default `output_path="docs/spec.md"` — review; may need lineage-aware default
- [ ] `lib/set_orch/profile_types.py` — review-learnings project-level path
- [x] `lib/set_orch/subprocess_utils.py` — PLAN_FILENAME env var handling
- [x] `lib/set_orch/state.py` — state load/save centralisation (review if it hardcodes paths)
- [x] `lib/set_orch/archive.py` — archive_and_write helper (generic; confirm no project-level assumptions)
- [ ] `lib/set_orch/agent/messaging.py` — messages dir (if applicable)

### 2.f — Legacy (4 files — deprecate or migrate)

- [x] `lib/set_orch/_api_old.py` — 17 refs (state, archive, report, events); decide: migrate OR formally deprecate in this change
- [x] `lib/set_orch/archive.py` (legacy) — confirm no hardcoded orchestration paths
- [x] `lib/set_orch/sentinel/findings.py` — findings path
- [ ] `lib/set_orch/sentinel/orchestrator.py` — state consume

### 2.g — Migrations + utilities (1 file)

- [x] `scripts/migrate-review-learnings.py` — review-findings path
- [ ] `scripts/*` — scan for any other hardcoded orchestration paths

---

## Phase 3 — Bash / Shell (28 files)

### 3.a — Core entry points (blocking)

- [x] `bin/set-orchestrate` — state + plan path derivation from env (multiple sites)
- [ ] `bin/set-sentinel` — spec argument → state
- [x] `bin/set-status` — reads state
- [ ] `bin/set-web` — serve wiring
- [ ] `bin/set-manager` — reads state
- [x] `bin/set-close` — worktree cleanup (extend with `--purge` + history)
- [x] `bin/set-new` — worktree init (no orch-path refs expected, confirm)
- [x] `bin/set-merge` — invokes merger; check for hardcoded state paths
- [x] `bin/set-harvest` — reads archive + state across projects
- [x] `bin/set-memory` — memory paths (cross-project, unrelated; confirm no orchestration-state refs)
- [x] `bin/set-project` — init path wiring
- [x] `bin/set-common.sh` — shared helpers (most likely the right centralisation point for Bash)

### 3.b — Legacy shell orchestration (12 files — deprecate or migrate)

- [ ] `lib/orchestration/dispatcher.sh` — directives, specs path
- [ ] `lib/orchestration/events.sh` — events append
- [ ] `lib/orchestration/config.sh` — config.yaml detection
- [ ] `lib/orchestration/digest.sh` — `DIGEST_DIR` default
- [x] `lib/orchestration/merger.sh` (if still referenced)
- [x] `lib/orchestration/verifier.sh` (if still referenced)
- [x] `lib/loop/engine.sh` — reflection READ
- [x] `lib/loop/state.sh` — state READ
- [ ] `lib/loop/prompts.sh` — reflection consume
- [ ] `lib/loop/hooks.sh` — state hook paths
- [ ] `lib/loop/watchdog.sh` — state path
- [ ] `lib/loop/events.sh` — events path

**Note**: if any `lib/orchestration/*.sh` or `lib/loop/*.sh` is no longer invoked (the Python cutover may have obsoleted them), mark `[/]` after confirming with `grep -rn <file-basename>` across `bin/` and production code.

### 3.c — Sidecar scripts (4 files)

- [ ] `scripts/debug-artifacts.sh`
- [ ] `scripts/debug-events-dir.sh`
- [ ] `scripts/audit-rules-sh.sh`
- [ ] `scripts/*` — remaining scans

---

## Phase 4 — YAML + other config (2 files)

- [ ] `modules/*/templates/set/orchestration/config.yaml.tmpl` (if present) — template-time, no runtime migration needed; ensure template docs reference `LineagePaths` rather than hardcoded dirs
- [ ] `templates/core/**/*.yaml` — check for path defaults

---

## Phase 5 — TypeScript / React (web frontend)

The web UI does NOT touch file paths directly — it goes through the API layer. Migration concern is purely the query-parameter plumbing (`?lineage=...`), already captured in tasks §13-14. Still, audit:

- [ ] `web/src/lib/api.ts` — confirm every fetch helper accepts + forwards `lineage` param
- [x] `web/src/pages/Dashboard.tsx` — confirm every data-fetching useEffect uses selected lineage
- [ ] `web/src/components/*` — each tab component: ActivityTimeline, TokensPanel, DigestPanel, PhaseView, ChangeTable, BattleView, SentinelPage, LogPanel, LineageList (new) — spot-check that none bypass the shared fetcher

---

## Phase 6 — Tests (12 files — update to use fixtures)

- [x] `tests/orchestrator/test-orchestrate-integration.sh` — 84 refs. Update to construct paths via a test helper that mirrors `LineagePaths`.
- [x] `tests/unit/test_state.py`
- [x] `tests/unit/test_state_journal.py`
- [x] `tests/unit/test_loop_state.py`
- [x] `tests/unit/test_worktree_harvest.py`
- [x] `tests/unit/test_archive_completed_to_jsonl.py` — already added; confirm it uses `LineagePaths`
- [x] `tests/unit/test_load_archived_changes.py` — already added; confirm it uses `LineagePaths`
- [x] `tests/unit/test_archive.py`
- [x] `tests/unit/test_issue_state_machine.py`
- [x] `tests/unit/helpers.sh` — shared test helper; extend with `LineagePaths`-equivalent bash helper
- [x] `tests/unit/test_orch_state.sh`
- [ ] Add `tests/unit/test_lineage_paths.py` — new, covers every property + lineage slug edge cases

---

## Phase 7 — Documentation sweep (non-blocking for archive)

The 290 markdown/doc references are mostly in:

- `openspec/specs/**/*.md` — existing specs that mention orch paths in prose; update after code migration is green
- `docs/` — user-facing guides
- `.claude/` — skill + rule files
- `templates/core/rules/*.md` — rules deployed to consumer projects
- `modules/*/templates/**/*.md` — module-specific templates

Migration approach for docs: after the code migration is complete and validated, a single sweep replaces hardcoded path fragments in prose with either the centralised reference (e.g., "the project's orchestration state, accessible via `LineagePaths.state_file()`") or leaves them as-is when they are genuinely path-name references (e.g., "the `orchestration-state.json` file is written by the engine").

Docs migration does NOT block this change from archiving — it runs as a separate, time-bounded cleanup pass after code is green.

---

## Verification gate

The verify script for this change SHALL:

1. Run `grep -rn` for every one of the 18 hardcoded patterns across the 107 code files.
2. For each `[ ]` row above where the grep still returns a match NOT via `LineagePaths`, the row remains unchecked and the verify gate BLOCKS archiving with a listing of residuals.
3. Produce a diff-style report showing which sites were migrated since the audit snapshot.
4. Accept `[~]` and `[/]` as terminal states for rows that don't need code changes (read-only constants or deleted files).

Audit snapshot timestamp: baseline at change-planning time. Refresh the snapshot after Phase 2 + Phase 3 are code-complete to confirm no new sites leaked in during implementation.

---

## Hotspot triage (by reference count within code files)

1. `lib/set_orch/_api_old.py` — 17 refs
2. `lib/set_orch/engine.py` — 13 refs
3. `lib/set_orch/supervisor/daemon.py` — 13 refs
4. `lib/set_orch/cli.py` — 11 refs
5. `lib/set_orch/merger.py` — 10 refs
6. `lib/set_orch/api/orchestration.py` — 10 refs
7. `lib/set_orch/dispatcher.py` — 9 refs
8. `lib/set_orch/planner.py` — 8 refs
9. `lib/orchestration/dispatcher.sh` — 5 refs
10. `bin/set-orchestrate` — 4 refs

Refactor order: implement `LineagePaths` first (Phase 1), migrate the top 10 hotspots (Phase 2.a + 2.c core subset), then sweep the long tail. Each hotspot is migrated in a single commit with a clear "before/after" diff so regressions are bisectable.
