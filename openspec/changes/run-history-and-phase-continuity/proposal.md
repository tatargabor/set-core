## Why

A single orchestration run produces history across several time horizons — initial plan execution, mid-run replans, and (if the operator relaunches the sentinel with an updated input) entirely new sentinel sessions. Today every UI tab except Changes/Phases silently **forgets** most of that history:

- Event/activity stream JSONL is rewritten on replan — the Activity timeline only shows the current cycle.
- Token breakdown reads Claude session files via the live `worktree_path`; once a worktree is cleaned up (`.removed.*`), its sessions become unreachable and the change disappears from the Tokens tab.
- Spec coverage and the per-change E2E manifest are regenerated each merge and keep only the current-plan view — requirements that were satisfied by archived changes lose their "merged" attribution.
- Phase numbering restarts on every sentinel session. A v2 design delivered to the same project reboots counting to Phase 1, making it impossible to tell at a glance that Phase 3 is "second-session work on top of a first-session foundation."

The fix for `_load_archived_changes` (already landed) only makes archived changes **visible in the Changes/Phases tabs**. Operational tabs still assume one cycle = the world, so a long-running project (multi-replan + multi-sentinel) looks like a fresh run. This change establishes a single, archive-centric history surface that every tab reads, and a phase-numbering convention that is stable across sentinel restarts.

## What Changes

- **Rotate orchestration event files on every replan and sentinel-stop** (`orchestration-events-cycle<N>.jsonl`, `orchestration-state-events-cycle<N>.jsonl`). The activity/LLM-calls APIs MUST concatenate all rotated files in chronological order.
- **Persist session summaries into the archive entry** when a change is archived (call count, total input/output/cache tokens, first/last call timestamp, duration). The Tokens tab and LLM-calls API MUST surface archived-change data from these summaries when the worktree session dir is gone.
- **Append-only coverage history** — write every merge-time coverage snapshot to `spec-coverage-history.jsonl` alongside the regenerated `spec-coverage-report.md`. The Digest/Reqs view MUST attribute covered requirements to the archived change that merged them.
- **Append-only E2E manifest history** — each merged change's `e2e-manifest.json` is appended to `e2e-manifest-history.jsonl` (one line per merge). The Digest/E2E subtab MUST aggregate tests across cycles and label each block with its source change.
- **Spec-lineage as the primary grouping key**. Every orchestration run is tagged with a `spec_lineage_id` derived from the input spec path (the `--spec` value the sentinel was started with — e.g., `docs/spec-v1.md` vs `docs/spec-v2.md`). All replans and sentinel restarts that target the **same** input spec belong to the same lineage. A **new** input spec opens a new lineage. Every rotated event file, archive entry, coverage history line, and E2E manifest history line carries its lineage id, so the Activity / Tokens / Digest / E2E tabs can render `v1` and `v2` content separately instead of overlapping them.
- **Continuous phase numbering WITHIN a lineage, fresh numbering BETWEEN lineages**. When a replan or sentinel restart targets the current lineage, phase numbers MUST be offset to continue monotonically from `max(lineage_archived_phase) + 1`. When a new lineage opens (operator starts sentinel with a different input spec), phase numbers MUST start fresh from the planner's native numbering — v2 phase 1 is NOT a continuation of v1 phase N.
- **Sentinel session tracked as a sub-dimension** (`sentinel_session_id`, `sentinel_started_at`) for within-lineage restart visibility, but lineage is the primary grouping key in every UI and API surface.
- **Backfill migration for existing runs** — a one-off migration step inspects `orchestration-plan.json::input_path` for every project, derives the lineage id, and rewrites `state-archive.jsonl` entries (and rotated event header rows, where present) to carry `spec_lineage_id` + `phase` where it is recoverable. After migration there is no `__legacy__` bucket and no `phase = 0` fallback; every historic record is attributed to its real lineage. Projects without a recoverable `input_path` (corrupt or missing plan file) are flagged in the API response so the operator can decide whether to purge them manually.
- **Retain `.removed.*` worktree metadata** in `worktrees-history.json` so historic session JSONL paths remain resolvable. Physical cleanup of `.removed.*` becomes explicit (`set-close --purge`), not automatic-at-merge.
- **Plan-version subgrouping** in the Phases UI when two cycles place changes under the same phase number (Phase N / cycle A, Phase N / cycle B).
- **Lineage list in the left sidebar** (under the project name in the sidebar's Project section — the same menu that currently lists Orchestration / Issues / Memory / Settings). Each known lineage appears as its own clickable entry showing the spec file's display name. Clicking an entry loads that lineage into the main pane. Default selection when a project is first opened: the **live** lineage if the sentinel is running, otherwise the lineage with the most recent activity. The lineage identity comes from `input_path`, which is already persisted in `orchestration-plan.json` — no new capture step is needed. An "All lineages" option is available at the top of the lineage list for a merged historical view.
- **Live + historic lineage browsing simultaneously.** While the sentinel actively runs on `spec-v2.md`, the operator MUST still be able to switch the selector to `spec-v1.md` and inspect that lineage's completed changes, timeline, tokens, coverage, and e2e results without interrupting v2's execution. Lineage filtering is a pure presentation-layer concern — the sentinel is agnostic to which lineage the operator is viewing.

### New Capabilities
- `run-history-archive`: the source-of-truth historical surface — rotated event streams, archived session summaries, coverage-history JSONL, e2e-manifest-history JSONL, worktree-history index, and archive-aware API readers that expose the full project timeline regardless of worktree cleanup or replan. Every history record is tagged with `spec_lineage_id` so it can be filtered without loss.
- `phase-continuity`: rules and state fields that keep phase numbering monotonic WITHIN a spec lineage across replans and sentinel restarts, and reset numbering BETWEEN lineages. Lineage identity is derived from the input spec path.
- `lineage-selector`: left-sidebar control (under the project name in the same menu that hosts Orchestration / Issues / Memory / Settings) that lists every lineage discovered in the project history, defaults to the live lineage when available (otherwise the most-recently-active one), and drives a filter that every data tab honours. Supports switching to a completed lineage while the sentinel is live on a different lineage.
- `coverage-lineage-scoping`: coverage is computed against each lineage's OWN spec scope, not the full project surface. If a lineage's spec defines 5 requirements, the coverage denominator is 5; prior lineage work does not pre-fill coverage even when the on-disk code already satisfies older requirements. This gives each lineage a truthful "how much of WHAT I PROMISED did I deliver" answer.

### Modified Capabilities
- `activity-timeline-api`: reader gathers events from every rotated cycle file, not only the live file, and includes sentinel-session boundary markers.
- `orchestration-token-tracking`: token aggregation includes archive-entry token fields and session summaries, no longer depends on live worktree presence.
- `spec-coverage-report`: coverage regeneration appends to history JSONL before overwriting the report; history is authoritative for "who merged this REQ".
- `worktree-e2e-lifecycle`: per-change `e2e-manifest.json` writes also append to the project-level history JSONL at merge time.

## Impact

- **Affected code**:
  - `lib/set_orch/engine.py` — event rotation hook on replan + sentinel stop; extend `_archive_completed_to_jsonl` with session summary + stop mutating `phase` default at read time.
  - `lib/set_orch/merger.py` — append to coverage-history + e2e-manifest-history on each successful merge.
  - `lib/set_orch/planner.py` — phase offset calculation on replan and on new sentinel start.
  - `lib/set_orch/api/helpers.py` — drop `phase = 0` legacy default; add `_archive_source` marker.
  - `lib/set_orch/api/activity.py` — read rotated events, emit sentinel-session markers.
  - `lib/set_orch/api/orchestration.py` — token/coverage/e2e endpoints archive-aware.
  - `bin/set-close`, worktree cleanup path — write `worktrees-history.json`, accept `--purge`.
- **Affected UI**:
  - Left sidebar (`web/src/components/AppShell.tsx` or equivalent) — new `LineageList` section under the project name listing every lineage with a live-indicator dot on the running one; selection drives the rest of the dashboard.
  - `web/src/components/ActivityTimeline.tsx` — render multi-cycle timeline with session-boundary separators.
  - `web/src/components/TokensPanel.tsx` — include archived-change tokens; visually mark archived rows.
  - `web/src/components/DigestPanel.tsx` — attribute each REQ to the change that merged it within the current lineage; show lineage-own E2E test blocks.
  - `web/src/components/PhaseView.tsx` — phase numbers reset per lineage; subgrouping when multiple cycles share a phase number within a lineage.
- **Affected artifacts**:
  - Project run dir gains `orchestration-events-cycle<N>.jsonl`, `spec-coverage-history.jsonl`, `e2e-manifest-history.jsonl`, `worktrees-history.json`.
  - `state-archive.jsonl` entries grow a `session_summary` field and drop the implicit-phase-0 fallback.
- **Backwards compatibility**: legacy `state-archive.jsonl` entries (no `phase`, no `session_summary`) remain readable and are surfaced under "Previous cycles"; no migration step is required on existing runs.
- **Non-goals**: this change does NOT redesign how replan triggers decide *which* changes to keep (that's planner behavior, out of scope), and does NOT build a separate "history viewer" route — all history is surfaced through the existing tabs.
