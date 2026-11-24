## Context

The Activity dashboard ([`web/src/components/ActivityView.tsx`](../../../web/src/components/ActivityView.tsx)) renders a per-category Gantt timeline whose rows are populated by [`lib/set_orch/api/activity.py`](../../../lib/set_orch/api/activity.py)'s `_build_spans` reducer. The `implementing` category appears as one row per change, produced from `STEP_TRANSITION` events (or a `DISPATCH`-based fallback). The span carries no internal structure today — a 30-minute `implementing` row is a single block.

The data needed to break it down is already produced server-side by [`lib/set_orch/api/activity_detail.py`](../../../lib/set_orch/api/activity_detail.py), which parses the agent's session JSONLs into per-tool sub-spans (`agent:tool:edit`, `agent:tool:bash`, `agent:subagent:<purpose>`, etc.). Each sub-span carries `detail.preview` — the originating file path or Bash command excerpt, truncated to 60 characters. The data is mtime-cached at `<project>/set/orchestration/activity-detail-v2-<change>.jsonl` and rebuilt on session-JSONL change.

`activity.py` already imports the drilldown helpers (`_build_sub_spans_for_change`, `_clip_and_filter`, `_compute_aggregates`) inside the existing enrichment pass (lines 1152–1206) and uses them to attach `llm_calls` / `tool_calls` / `subagent_count` aggregates to every `implementing` span. The integration point for our work is exactly there: same enrichment block, same cached input data, one additional helper that returns categorized merged ranges.

We earlier designed a hook-based "live event emission" alternative (`SUB_PHASE_TRANSITION` events written by an extended `set-hook-activity`). It was rejected during hardening review because the event path required mitigations across nine independent failure modes (PID reuse, hook exit-0 enforcement, event-line atomic-append bound, KNOWN_EVENT_TYPES extension, deploy-side migration of two heredocs in `bin/set-deploy-hooks`, project-root cache, verifier/sentinel session opt-out, change-name resolution, redaction at the wire level) — each adding complexity to the agent's tool execution path for a sub-second freshness gain over the server-side approach. The trade was unfavourable: stable agent operation is the higher-value invariant.

## Goals / Non-Goals

**Goals:**
- Visible breakdown of `implementing` time into spec / code / test / build / subagent / other on the main Activity timeline, without requiring a per-change drilldown click.
- Zero agent-side touchpoints — no hook changes, no new event types, no settings.json updates, no consumer redeploy.
- Retroactive coverage — old runs render with the same nested breakdown as new ones because the source data (session JSONLs + drilldown cache) exists for every prior run.
- Fully additive on every contract surface (API output, frontend rendering). A run with no session-derived sub-spans renders identically to today.
- Use the existing drilldown cache and enrichment plumbing — no new file paths, no new readers, no new reducer state.

**Non-Goals:**
- Sub-phase decomposition for `planning` or `fixing` lifecycle phases.
- Sub-agent internal breakdown (still in the per-change drilldown's `agent:subagent:*` lane).
- Live thinking / `agent:llm-wait` spans on the main timeline.
- Read / Grep / Glob as separate sub-phases.
- Sub-spans summing exactly to the parent's duration. Waits, gaps, hook overhead, and LLM-think time are intentionally excluded — `sub_spans` represents deliberate classifiable agent work, not a time-coverage decomposition.
- A user-configurable taxonomy or custom classification rules.
- Replacing the existing drilldown's per-tool view — the live sub-phases summarize, the drilldown details.

## Decisions

### D1. Server-side classification, not live event emission

The drilldown already reconstructs per-tool sub-spans from session JSONLs and caches them per change with mtime invalidation. Surfacing a categorized rollup of that data on the main timeline costs one helper function and runs inside the enrichment pass that already loads the same data for the existing `tool_calls` / `subagent_count` aggregates.

The earlier-considered alternative — an agent-side hook emitting `SUB_PHASE_TRANSITION` events to the canonical event stream — was rejected because the hook path required mitigations across PID reuse, exit-0 enforcement, atomic-append bounds, deploy-side migration, KNOWN_EVENT_TYPES registration, project-root caching, change-name resolution, verifier/sentinel session opt-out, and trigger redaction. Each was a real failure mode to design around for a sub-second freshness improvement that operators do not perceive at the dashboard's ~5-second poll interval. Server-side classification trades that freshness for zero new failure modes and retroactive coverage of historical runs.

### D2. Six-bucket taxonomy at the operator-facing layer

The categories visible to operators are: `spec`, `code`, `test`, `build`, `subagent`, `other`. The mapping over the drilldown's existing categories is:

```
agent:tool:edit  | agent:tool:write | agent:tool:multiedit
   detail.preview path startswith openspec/changes/  → spec
                                or openspec/specs/   → spec
   else                                              → code

agent:tool:bash
   detail.preview matches test pattern               → test
   detail.preview matches build pattern              → build
   else                                              → other

agent:subagent:*                                     → subagent

agent:tool:read | agent:tool:grep | agent:tool:glob
agent:tool:webfetch | agent:tool:websearch | agent:tool:other
agent:tool:notebookedit | agent:tool:todowrite       → other
```

Pattern regexes (case-insensitive, word-boundary-anchored):
- test: `\b(pytest|jest|vitest|playwright|npm\s+(run\s+)?test|yarn\s+test|pnpm\s+(run\s+)?test|go\s+test|cargo\s+test)\b`
- build: `\b(npm\s+run\s+build|next\s+build|tsc|cargo\s+build|make\s+(build|all)|bun\s+build)\b`

The taxonomy is intentionally narrow. Operators decide on "is the agent doing OpenSpec work or real code? is it stuck in tests?"; finer splits (read vs grep, git vs cat) do not change operator behaviour and would multiply rows for parallel-change views without informational gain.

**Alternative considered:** finer split with separate `read` and `git` categories. Rejected as not actionable — the v1 taxonomy can grow if a category proves load-bearing.

### D3. Excluded sub-span types and the "sub-spans don't sum to parent" property

`agent:llm-wait`, `agent:gap`, `agent:hook-overhead`, `agent:loop-restart`, `agent:review-wait`, `agent:verify-wait` are all dropped from the rollup. They represent waits or orchestrator-imposed time, not deliberate classifiable agent work. As a consequence the union of `sub_spans` does not necessarily cover the parent's `[start, end]` window — there will be uncovered time inside long parents.

This is a deliberate design property and is documented in both the API spec and the frontend (a tooltip on the parent row's duration explains "x% classifiable work; remainder is wait/think time"). Operators get a clean picture of *what work was done* without the timeline being dominated by think-time green segments.

**Alternative considered:** include `agent:llm-wait` as a `thinking` sub-phase. Rejected — operators do not decompose think-time and including it would dominate every parent (~50% of typical implementing windows).

### D4. Consecutive-merge rule

The drilldown emits one sub-span per tool invocation. A 30-minute parent with 200 Edit calls would translate to 200 micro-spans on the timeline — visually noisy and slow to render. Consecutive sub-spans of the same category are merged into single ranges, gap-tolerant up to a small threshold:

- Two sub-spans `A` (category=C, end=t1) and `B` (category=C, start=t2) with `t2 - t1 ≤ 30 sec` collapse into one range `[A.start, B.end]`.
- The first sub-span in a merged range provides `trigger_tool` and `trigger_detail`; subsequent triggers are dropped (the merged range gets one representative trigger).
- The 30-second tolerance comes from the same `GAP_THRESHOLD_MS` the drilldown uses to ignore inter-turn latency.

**Alternative considered:** no merging, render every micro-span. Rejected for visual noise and frontend perf. Operators look at runs of work, not individual tool calls.

### D5. Frontend rendering: nested expand/collapse, not flat replacement or single-row segmentation

(Preserved from earlier design.) Three options were sketched:
- α (flat: 6 sub-rows replace the parent) — explodes for 5 parallel changes; rejected.
- γ (single row, colour-segmented) — keeps row count low but loses time precision and fails when two sub-phases are simultaneously active across changes.
- β (parent row stays, ⌃/▼ toggle on the label, indented sub-rows when expanded) — multi-change views readable by default, progressive disclosure, matches drilldown UX.

Default state: collapsed. Per-change expand state in `localStorage` keyed by change name.

### D6. Cache reuse, no new cache file

The classification helper reads from `_build_sub_spans_for_change(project_path, change_name)` — the same call the existing enrichment block already makes. No new cache file, no new mtime checks, no new path resolver. The classifier is pure: given the windowed sub-span list and the parent's `(start, end)`, it returns the merged categorized list deterministically.

### D7. Verifier sessions excluded automatically

The drilldown's `_find_session_files` already excludes orchestrator-side verifier sessions (those with `[PURPOSE:<purpose>:<change>]` prefix in the first user message — see `activity_detail.py:491-505`). Verifier work is represented on the main timeline as `llm:<purpose>` spans from `LLM_CALL` events, separate from `implementing`. Our classifier operates on the drilldown's already-filtered output, so verifier sessions are excluded from the rollup with no extra logic.

### D8. Trigger metadata: `trigger_detail` is `detail.preview` from the drilldown

The drilldown already truncates `command` / `file_path` / `description` to 60 characters when populating `detail.preview` (`activity_detail.py:299`). For our `trigger_detail` field we pass `detail.preview` through unchanged. After consecutive-merge, the first sub-span's preview wins — operators see "what kicked off this run of work". No additional redaction is needed because the drilldown's 60-character cap already bounds line length and limits the chance of secret material appearing.

### D9. Frontend rendering hardening: sub_spans always a list

The API response always sets `sub_spans: list[dict]`. When no classifiable work is present, the value is `[]`. The frontend treats `null`, `undefined`, or missing field as `[]` defensively — older API responses or transient errors never trigger an exception path in the renderer.

## Risks / Trade-offs

- **Sub-spans don't cover the full parent duration** → by design (D3); documented at the API and frontend layers. The operator's "percent classified" tooltip surfaces this directly so there's no surprise.
- **5-second freshness floor** → the dashboard's poll interval, not the classifier itself. Operators do not watch second-by-second, and the existing aggregates already had this property.
- **Drilldown cache mtime races** → the classifier inherits whatever the drilldown cache returns. If the cache is stale, the breakdown is stale. The drilldown's existing mtime-invalidation already covers the live case (session JSONLs are append-only; mtime advances on every flush).
- **Heuristic regex coverage** → custom test scripts (`make e2e-flavor-x`) fall into `other`. Operators see "agent is doing ambient work", which is no worse than today's "no breakdown at all". Patterns can be extended over time without contract changes.
- **Sub-agent internal time is one segment** → a Task tool dispatch becomes one `subagent` segment for its full duration. The drilldown still shows the inner breakdown via `agent:subagent:*` linked sessions; operators who want detail click in.
- **Consecutive-merge can hide context switches** → if the agent flips Edit ↔ Bash ↔ Edit within 30 seconds, the merge collapses across the brief Bash. The drilldown preserves per-call detail; the main-timeline rollup is by design summarized.
- **Frontend regression on nested rendering** → expand/collapse changes the Gantt's vertical layout dynamically. Default-collapsed state means at-rest layout matches today; expansion is opt-in per change; existing Playwright tests for the Activity view continue to pass without modification.

## Migration Plan

No data migration. The change rolls forward as follows:

1. **Land core change** — `lib/set_orch/api/activity.py` enrichment extension and `lib/set_orch/api/activity_detail.py` classifier helper. After landing, existing runs immediately get the classified breakdown on next API poll because the source data already exists in the per-change drilldown cache.
2. **Land frontend change** — `web/src/components/ActivityView.tsx` nested rendering with expand/collapse and `localStorage` persistence.
3. **Backward compat verification** — load an old project's data: `implementing` rows get the breakdown automatically. Load a new run in an old dashboard: extra field is ignored.
4. **No rollback machinery needed** — disabling the feature is removing the classifier helper call from the enrichment block; no schema downgrade, no data deletion, no consumer-side action.

## Open Questions

- Should the parent row's tooltip also show the per-category percentage breakdown numerically (e.g., "spec 18% · code 47% · test 12% · build 4% · subagent 5% · other 14%")? Likely yes — surfaces the data even when collapsed. Adding to the tasks.
- Should the consecutive-merge tolerance (30 sec) be configurable, or is one fixed value enough for v1? Default: fixed; revisit if real runs surface a need.
- Should we add a "percent classifiable" indicator to make D3's "doesn't cover full duration" property visible? Yes — a small footnote-style label on the parent row when expanded.
