## Context

The orchestration framework currently treats "history" as a cycle-local concept. Every major artefact — event streams, per-change session dirs, coverage reports, E2E manifests, phase numbers — is written as if the current cycle were the whole project. Replan overwrites event streams; worktree cleanup removes the Claude session JSONLs that the Tokens panel relies on; coverage regeneration loses track of who first merged a requirement; phase numbering resets on every sentinel relaunch. The fix for `_load_archived_changes` (path + flat parsing) exposed archived rows in the Changes/Phases tabs but left every other tab in the dark — you can SEE that phase 0 changes exist, but the Activity timeline, Tokens, Digest, and E2E views behave as if only the current cycle's work ever happened.

This change builds a single archive-centric history surface that all those tabs share, plus a phase-numbering convention that stays monotonic across replans AND across fresh sentinel sessions (e.g., when the operator relaunches the sentinel with a v2 design).

Constraints:

- **Backwards compatibility is mandatory**. Runs created before this change have malformed or partial archive entries (no `phase`, no `session_summary`, no rotated events, no history JSONLs). They must still render — just under a "Previous cycles" bucket rather than pretending to be a real phase 0.
- **Append-only, never-rewrite** for the history JSONLs. A corrupt line must not poison the whole file; readers skip malformed lines with a WARNING.
- **No new UI routes**. Everything surfaces through the existing Changes/Phases/Activity/Tokens/Digest tabs — this is a data-completion project, not an information-architecture redesign.
- **Minimal invasive change on the hot path**. Rotation, session summarization, and history appends happen at cycle/merge boundaries, not in the per-iteration loop.

## Goals / Non-Goals

**Goals**
- Every orchestration tab (Activity, Tokens, Digest, E2E, Phases) reflects the full project history, including archived and pre-replan work.
- Phase numbers are monotonic across replans and across sentinel sessions — Phase N always means something stable.
- `.removed.*` worktrees retain enough metadata to let the Tokens/LLM-calls API render their historic sessions.
- Legacy runs render cleanly under "Previous cycles" without pretending to be a first-class phase 0.

**Non-Goals**
- Redesigning how the planner decides which changes to keep on replan — that's a planner concern, out of scope.
- Building a dedicated history viewer page or timeline explorer — existing tabs carry the load.
- Cross-project history (rolling up multiple projects into one view).
- Full migration of legacy archives to the new shape — they keep working via fallback paths.

## Decisions

### D1: Event rotation on cycle/session boundary, not on every write

**Choice**: Rotate `orchestration-events.jsonl` (and its state-events sibling) once, atomically, at the start of `_auto_replan_cycle` and at sentinel clean-stop. Readers glob `orchestration-events-cycle*.jsonl` and concatenate in cycle order.

**Alternatives considered**:
- *Write append-only to a single ever-growing file*. Rejected — existing code and ops assume the live file is the current cycle; mixing cycles inside one file would require rewriting every consumer and breaks the sentinel's tail-follow UX.
- *Store events in SQLite*. Rejected — too large a refactor for the observed problem; JSONL rotation is the minimal viable fix and matches the existing `state-archive.jsonl` pattern.

### D2: Persist a session summary on archive, not the full session JSONL

**Choice**: On `_archive_completed_to_jsonl`, scan the worktree's Claude session dir, compute aggregates (`call_count`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_create_tokens`, `first_call_ts`, `last_call_ts`, `total_duration_ms`), and embed them as `session_summary` on the archive entry. The full JSONL stays in the `.removed.*` worktree; full per-call drill-down remains available only if the operator has not yet run `--purge`.

**Alternatives considered**:
- *Copy the JSONL contents into the archive*. Rejected — session JSONLs can be 10s of MB per change; inlining them into `state-archive.jsonl` destroys the ability to stream that file.
- *Move the JSONL into a project-level history dir*. Tempting, but adds filesystem cost, complicates permissions, and breaks Claude Code's "your session file is at `~/.claude/projects/-mangled/...`" contract. Keep the summary in the archive; keep the raw JSONL where it was written.

### D3: Monotonic phase numbering via offset, computed at plan-write time

**Choice**: Before writing a new plan (replan or fresh sentinel session), compute `offset = max(phase across live state + archive entries) - min(phase in new plan) + 1` and apply it to every change's `phase` field. Offset of 0 means "no shift needed" (the natural case for a brand-new project).

**Why the offset is at plan-write time**: keeps the planner itself unaware of history — it continues to number phases from 1 based on dependencies. Phase continuity becomes a framework concern, not a planner concern, which is cleaner architecturally.

**Alternatives considered**:
- *Seed the planner with a minimum phase number*. Rejected — couples the planner to state-archive shape. Offset-after-plan is purely mechanical and keeps the planner decoupled.
- *Separate "run number" instead of shifting phases*. Rejected — creates an extra dimension in the UI that users don't want to think about. Phase is the primary operator concept; keeping it monotonic matches user intuition.

### D4: Plan-version carry-through for same-phase cycle collisions

**Choice**: Every archive entry carries `plan_version` (already done in the landed fix). The UI groups archive+live entries by `(phase, plan_version)` when two plan versions share a phase number; otherwise the grouping is by phase alone (the common case).

This covers the edge case where offset did NOT fire (for example, replan dropped all prior phase 1 changes as skipped, and the new plan reuses phase 1 because nothing live carried it forward) — the archived entries still belong to plan version X, the new ones to plan version X+1, and the UI visibly separates them.

### D5: `.removed.*` retention is explicit, purge is a deliberate action

**Choice**: The current `cleanup_worktree` path renames to `.removed.<epoch>` and stops. This change adds `worktrees-history.json` append so the API knows which `.removed.*` paths exist and which change they belonged to. Physical deletion only happens via `set-close --purge` (explicit operator action) or an eventual retention-policy job (not built in this change).

**Rationale**: historic session JSONLs are too valuable for debugging and for the Tokens/LLM-calls tabs to delete silently. Keeping `.removed.*` on disk is cheap relative to the context it provides when a change stalls months after the fact.

### D6: Spec lineage identity is the input path, phase continuity is lineage-scoped

**Choice**: Use the normalised `input_path` (the `--spec` argument the sentinel was launched with) as `spec_lineage_id`. All replans and sentinel restarts targeting the same path belong to the same lineage; a different path opens a new lineage. Phase offset computation reads only records tagged with the current lineage — v1's phases do not leak into v2's numbering.

**Alternatives considered**:
- *Use `input_hash` of the spec content*. Rejected — operators routinely edit a spec file in place between runs (typo fixes, scope additions); they expect continuity, not a new lineage each time. Path-based identity matches intent.
- *Use a `--lineage-id <name>` CLI flag*. Rejected — adds operator overhead for the common case (one spec file = one lineage); path-based default gets the right behaviour without asking.
- *Derive lineage automatically from some "root change" relationship*. Rejected — fragile, depends on whichever change happens to merge first.

The v1/v2 pattern the operator described ("edit a new `spec-v2.md`") is supported naturally: renaming the file changes the path, which opens a new lineage. Editing `spec.md` in place keeps the same path, which keeps the same lineage — a refinement, not a restart.

### D7: Lineage list lives in the left sidebar, filter is presentation-only

**Choice**: The lineage selector is the existing project sidebar's new `Lineages` section, placed between the project name header and the current `Orchestration / Issues / Memory / Settings` items. Each discovered lineage is a clickable row; a green dot marks the live one. Default selection on first load is the live lineage if the sentinel is running, otherwise the lineage with the most recent activity (`max(last_seen_at)`). Selection persists in `localStorage`. The filter is a purely client-side selection, translated into a `?lineage=<id>` query parameter on data fetches.

The sentinel has no concept of "which lineage the operator is viewing" — it always runs on `state.spec_lineage_id`, and the StatusHeader's live status badge always reflects that regardless of which lineage is in the sidebar's highlighted row. A text hint ("Viewing v1.md — sentinel running v2.md") appears next to the badge whenever the two differ, so the operator cannot mistake the view for the running target.

**Why sidebar over header dropdown**: the operator wants lineages to feel like peers of the other sidebar items (Orchestration / Issues / Memory / Settings) — they are navigation-level, not a buried dropdown control. Putting them in the sidebar matches the existing mental model and gives each lineage a persistent visual anchor.

**Alternatives considered**:
- *Dropdown in the dashboard header*. Rejected — hides lineages one click behind, and hurts the "I want to glance and see what runs exist" scan.
- *Per-lineage websockets and data streams*. Rejected — over-engineered. Existing per-project websocket already sends state updates for the live lineage; historic lineages are static after merge, so polling REST on selector change is sufficient.
- *Make clicking a lineage change the sentinel's target spec*. Rejected — conflates view with control. If the operator wants to change the sentinel's target they stop-and-restart with a different `--spec`.

### D7a: Coverage is scoped to the lineage's own spec denominator

**Choice**: Each lineage's coverage is computed ONLY against the requirements declared in that lineage's input spec — not against the project's historical spec union, and not against "what already exists on disk." The denominator for v2 is whatever v2's spec asks for; v1's prior work does not pre-fill v2's coverage even if the artefacts v1 produced are still on disk and technically satisfy older requirements.

**Rationale**: operators work lineage-at-a-time. When they open v2, the useful question is "how much of the v2 promise did I keep," not "what has the project in totality ever covered." A fresh lineage that only adds one screen should report 100% when that screen's REQs are met, not 1/N% where N is the whole project's REQ count.

**Alternatives considered**:
- *Union denominator across all lineages*. Rejected — creates a misleading low-coverage reading every time the operator makes a focused follow-up lineage.
- *Filesystem-inspection-based coverage ("is the code there?")*. Rejected — fragile and opinionated. Coverage is about the plan-and-merge contract within a lineage, not about static analysis of generated code.
- *Allow operators to opt a lineage into "inherit from v1"*. Deferred — could be added later via a spec-file directive, but not in this change. The default (no inheritance) matches the focused-follow-up mental model.

### D7b: Legacy runs are migrated, not preserved as a synthetic bucket

**Choice**: The framework ships with an idempotent backfill migration that opens every project's `state-archive.jsonl`, reads `orchestration-plan.json::input_path`, and rewrites archive entries to carry `spec_lineage_id` + `phase` wherever attribution can be recovered. Entries that cannot be attributed (missing plan file, no prior snapshots) become `spec_lineage_id = "__unknown__"` — a minority corner, not the default surface.

**Why migrate rather than fall back**: operators experienced the mislabeling in the craftbrew-1719 run where replan-skipped changes were lumped under "Phase 0." Migration gives them the correct picture on the first load after upgrade. A fallback bucket ("__legacy__") would persist the same confusion indefinitely.

**Trade-off**: one-time write to every project's archive file. Migration is guarded by an idempotency check (skip entries that already have `spec_lineage_id`), safe to run multiple times, and logged so operators can inspect what changed.

### D8: History writes are best-effort, never block the happy path

**Choice**: Every new write (event rotation, coverage history append, e2e manifest history append, worktree history append, session summary capture) is wrapped in a `try/except OSError` with a WARNING log. If history writing fails (disk full, permission error, file lock contention), the operational flow (merge, replan, cleanup) continues.

**Trade-off**: a failed history write leaves a hole in the record. The WARNING log makes the hole detectable post-hoc. The alternative — failing the merge because history write failed — would turn a benign I/O issue into a stuck orchestration. Benign holes are the better failure mode.

## Risks / Trade-offs

- **[Risk]** Rotated event files accumulate indefinitely over very long projects. → *Mitigation*: file counts stay bounded per sentinel session in practice (replans are rare — handful per session), and each file is sub-MB; no retention job needed in this change.
- **[Risk]** Session summary scan on archive adds seconds to replan. → *Mitigation*: only runs per-change-being-archived, not per-change-in-state; bounded to at most N calls × K changes on the slow path. Scanning is I/O only, no LLM call.
- **[Risk]** Phase offset could collide with operator expectations when they cancel a session and restart the same spec. → *Mitigation*: offset only shifts UPWARD; if the operator wants "fresh" numbering, they can start a new project dir. Monotonic numbering is the documented contract; restart-to-reset is out of scope.
- **[Risk]** Legacy archive entries that lack `session_summary` but point to a `.removed.*` worktree show `—` in the Tokens panel. → *Mitigation*: acceptable; the UI shows the archived row under "Previous cycles" with dash token values, which is accurate (we don't know the numbers). No synthetic zeros.
- **[Risk]** Cycle-aware grouping breaks existing Playwright selectors in the Phases tab. → *Mitigation*: introduce grouping only when more than one plan version is present for a phase; default rendering unchanged for single-cycle runs (the common case in all existing E2E fixtures).

## Migration Plan

No data migration required. The change is purely additive:

1. Deploy new archive writer — writes `session_summary`, `plan_version`, `sentinel_session_id` on new archive entries.
2. Deploy new archive reader — tolerates missing fields (legacy entries), stamps `_archive_source = "legacy"` on them.
3. Deploy event rotation — only fires at replan/sentinel-stop from this point forward; pre-existing runs that already rotated (or didn't) continue unchanged.
4. Deploy history JSONL appenders (coverage, e2e, worktrees) — empty files treated as "no history yet"; existing runs don't gain retroactive history but don't lose anything either.
5. Deploy phase offset — no-op when archive is empty or when all archive entries are `legacy` (which carry no explicit phase, so `max(...)` ignores them).
6. Deploy UI changes last — readers are new-format-tolerant; UI renders legacy under "Previous cycles" without breaking existing selectors.

Rollback: remove the feature flag that guards phase-offset and history-append — reader continues to work with or without the new fields. No data cleanup required.

## Open Questions

- **Q1**: Do we need a per-project GC policy for `worktrees-history.json` and rotated event files, or can it stay unbounded until a user explicitly runs `--purge`? Leaning toward "unbounded is fine" given observed project sizes; revisit if a project ever hits 100+ cycles.
- **Q2**: Should `_archive_source = "legacy"` be persisted into the archive entry itself (dedup so reader doesn't recompute) or computed every read? Leaning toward compute-every-read because it's cheap and lets us change the definition later without migration.
- **Q3**: Session-boundary markers in the Activity timeline — should they render as full-height dividers (like a column header) or as thin lane-spanning lines? Leave the decision to the UI implementation task; the API just emits the span, the component chooses the visual.
