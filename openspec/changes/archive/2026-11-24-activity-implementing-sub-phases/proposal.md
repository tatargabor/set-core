## Why

The Activity dashboard's `implementing` row currently absorbs every kind of agent work — OpenSpec artifact authoring, source-code edits, test runs, build runs, and sub-agent dispatches — into a single opaque span that often runs 30+ minutes. Operators watching a long-running orchestration cannot tell whether the agent is stuck writing spec, churning on code, or burning time in tests. The data we need to break this down already exists: the per-change drilldown (`activity_detail.py`) already reconstructs `agent:tool:edit/write/bash/...` and `agent:subagent:*` sub-spans from session JSONLs, including the originating file path or Bash command in each sub-span's `detail.preview`. It just isn't surfaced on the main timeline. This change classifies those existing sub-spans into a small operator-facing taxonomy and exposes the classified buckets as nested rows under the parent `implementing` lane — purely server-side, with no agent-side touchpoints, no new event types, and no consumer redeploy.

## What Changes

- The activity-timeline API extends each `implementing` span with a `sub_spans: list[dict]` field. The list is always present (empty when no session-derived sub-spans are available for that span's window), and each sub-span carries `category`, `start`, `end`, `duration_ms`, `trigger_tool`, and `trigger_detail`.
- A small classifier maps the existing drilldown sub-span categories into a six-bucket operator-facing taxonomy: `spec`, `code`, `test`, `build`, `subagent`, `other`.
- Consecutive same-category sub-spans within a parent's window are merged into single ranges so the rendered breakdown reads as runs of work, not a thicket of micro-spans.
- The web dashboard's Activity view renders `implementing` rows as expandable: the parent row continues to show the aggregate span; when sub-spans exist, the row label gains a collapse/expand toggle that reveals indented sub-rows in distinct color shades.
- Sub-span types that represent waits or non-classifiable work (`agent:llm-wait`, `agent:gap`, `agent:hook-overhead`, `agent:loop-restart`, `agent:review-wait`, `agent:verify-wait`) are excluded from the breakdown — the sub-span list represents only deliberate, classifiable agent work and does not necessarily sum to the parent's duration.

## Capabilities

### New Capabilities

- `activity-sub-phases`: server-side decomposition of the `implementing` lifecycle phase into typed sub-spans (spec / code / test / build / subagent / other), surfaced as expandable child rows under the parent `implementing` lane in the Activity dashboard. Owns the sub-phase taxonomy, the classification rules over existing drilldown sub-span categories, the consecutive-merge rule, and the rendering contract.

### Modified Capabilities

- `activity-timeline-api`: each `implementing` span gains an additional `sub_spans` field populated from a small classifier that runs as part of the existing `implementing`-span enrichment pass (`activity.py:1152-1206`); no event-stream contract changes, no new reducer state.

## Impact

- **Affected files (Layer 1 — core)**:
  - `lib/set_orch/api/activity.py` — extend the existing `implementing`-span enrichment block (currently at lines 1152-1206) to attach the classified `sub_spans` list alongside the existing `llm_calls` / `tool_calls` / `subagent_count` aggregates.
  - `lib/set_orch/api/activity_detail.py` — add a small `_classify_sub_phases(sub_spans, parent_window)` helper that reuses the existing windowed sub-span data, applies the six-bucket mapping, and merges consecutive same-category spans.
- **Affected files (Layer web — dashboard)**:
  - `web/src/components/ActivityView.tsx` — nested rendering: parent `implementing` row gains expand/collapse toggle when `sub_spans.length > 0`; six new sub-categories registered in `CATEGORY_COLORS` and `CATEGORY_LABELS`; expand state persisted in `localStorage`.
- **No agent-side changes**: no hook modifications, no new event types, no settings.json changes, no `set-deploy-hooks` updates, no consumer-project redeploy required. The classifier reads only from data that the drilldown is already producing for every existing run.
- **Backward compatibility**: fully additive. Old runs render with the same nested breakdown as new runs because the source data (session JSONLs and the per-change `activity-detail-v2-<change>.jsonl` cache) exists for every prior run. Old frontend with new API silently ignores the extra field. Old API with new frontend treats the missing field as an empty list. No data migration.
- **Latency**: the classifier runs on the existing `_build_sub_spans_for_change` cached output (mtime-validated), so the additional cost is O(sub_spans-in-window) per `implementing` span — negligible. The dashboard's typical poll interval (~5 sec) is the effective freshness.
- **Disjoint from in-progress changes**: `observability-event-file-unification` (already committed at `ff859a9d`) touches the event read-side resolver and `VERIFY_GATE` schema — disjoint regions of `activity.py` (we touch the enrichment pass at line ~1152, not the event resolver). `web-quality-gate-coverage` modifies the gate-counter UI (different region of the dashboard). No overlap.
- **Tests**: classifier unit tests covering each sub-phase mapping rule and the consecutive-merge logic; reducer integration tests asserting the `sub_spans` field shape on `implementing` spans; a Playwright test asserting expand/collapse behavior in the dashboard.
- **Out of scope**: live thinking / `agent:llm-wait` spans (excluded by design — not classifiable work); sub-agent internal breakdown (still in the per-change drilldown's `agent:subagent:*` lane); sub-phases for `planning` or `fixing` (only `implementing` is decomposed); Read/Grep/Glob as separate sub-phases (they fall into `other`); a user-configurable taxonomy.
