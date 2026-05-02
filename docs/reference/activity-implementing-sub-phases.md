# Activity dashboard — implementing sub-phase breakdown

The Activity tab's `implementing` row breaks down into a six-bucket
operator-facing taxonomy that surfaces *what kind of work* the agent did
inside each implementation phase. The breakdown is computed server-side
from the existing per-tool drilldown data — no agent-side hooks, no new
event types, no consumer-project redeploy.

## The six buckets

| Bucket      | Source signal                                                                 |
|-------------|-------------------------------------------------------------------------------|
| `spec`      | Edit/Write/MultiEdit on a path under `openspec/changes/` or `openspec/specs/` |
| `code`      | Edit/Write/MultiEdit on any other file path                                   |
| `test`      | Bash command matching `pytest\|jest\|vitest\|playwright\|npm test\|...`       |
| `build`     | Bash command matching `npm run build\|next build\|tsc\|cargo build\|make build\|bun build` |
| `subagent`  | Task / Agent tool dispatch (the parent's wait time, not the inner work)       |
| `other`     | Read, Grep, Glob, git, cat, and any Bash command not matching test/build      |

Excluded from the rollup (intentionally — these are not deliberate work):
`agent:llm-wait`, `agent:gap`, `agent:hook-overhead`, `agent:loop-restart`,
`agent:review-wait`, `agent:verify-wait`. Because of these exclusions the
sum of `sub_spans` durations does *not* equal the parent's duration —
the unclassified remainder is wait/think time. The parent-row tooltip
shows both the per-bucket percentages and the unclassified share so this
is transparent to operators.

## API surface

`GET /api/{project}/activity-timeline` returns an extra field on every
`implementing` span:

```json
{
  "category": "implementing",
  "change": "foundation-navigation",
  "start": "...",
  "end": "...",
  "duration_ms": 1454000,
  "detail": { "llm_calls": 7, "tool_calls": 58, "subagent_count": 1 },
  "sub_spans": [
    {
      "category": "spec",
      "start": "...",
      "end": "...",
      "duration_ms": 42000,
      "trigger_tool": "Edit",
      "trigger_detail": "openspec/changes/foundation-navigation/proposal.md"
    },
    { "category": "code", "...": "..." }
  ]
}
```

Contract:

- `sub_spans` is **always present** on every `implementing` span (empty
  list when no classifiable data is available, never `null` and never
  missing). Frontend treats `null` / missing / non-array as `[]` defensively.
- Adjacent same-category sub-spans within 30 seconds are merged into a
  single range — the first sub-span's `trigger_tool` and `trigger_detail`
  win; subsequent triggers in the merged range are dropped.
- Sub-span entries are sorted by `start` ascending and never overlap.
- Every entry is confined to the parent's `[start, end]` window.

## Frontend behaviour

The `implementing` row gets a tree-style toggle (`▼` expanded / `▶`
collapsed) on the left labels column when the API returns at least one
non-empty `sub_spans` list across the visible spans. **The toggle is
expanded by default** — operators almost always want the breakdown
visible. The collapse choice is persisted per-browser in `localStorage`
under `activity-implementing-sub-expanded`.

When expanded, six indented sub-rows appear under the parent in
declaration order (spec / code / test / build / subagent / other), each
in a distinct shade. Each sub-row shows the synthesized sub-spans for
that category aggregated across **every** change visible in the current
view — useful when running multiple changes in parallel (the common
sentinel case).

The parent-row tooltip shows the per-category percentages plus an
`unclassified N% (wait/think)` footer, so the design property "sub-spans
don't sum to parent duration" is visible without clicking through.

## Why server-side, not live event emission

The earlier candidate design emitted `SUB_PHASE_TRANSITION` events from
an extended Claude Code hook on the agent side. It was rejected during
hardening review because the hook path required mitigations across nine
independent failure modes (PID reuse, hook exit-0 enforcement,
`KNOWN_EVENT_TYPES` extension, deploy-side migration of two heredocs in
`bin/set-deploy-hooks`, project-root cache, verifier/sentinel session
opt-out, change-name resolution, atomic-append bound, redaction at the
wire level). Each was real work to make safe, in exchange for a
sub-second freshness gain over the server-side approach that operators
do not perceive at the dashboard's typical poll cadence.

Server-side classification:

- Adds zero new failure modes (extends existing enrichment pass with one
  helper call; failures fall back to `sub_spans: []` per existing
  defensive style).
- Works retroactively for **all** existing runs because session JSONLs
  already exist.
- Requires no consumer-project redeploy and no `set-project init` rerun.
- Reuses the same per-change drilldown cache that the existing aggregate
  enrichment already loads — at most one cache read per change per API
  request.

## File layout

| Path                                                                          | Role                                                       |
|-------------------------------------------------------------------------------|------------------------------------------------------------|
| `lib/set_orch/api/activity_detail.py`                                          | Classifier helpers + Bash regex constants + cache version  |
| `lib/set_orch/api/activity.py::_enrich_implementing_spans`                     | Extracted enrichment pass (testable in isolation)          |
| `web/src/components/ActivityView.tsx`                                          | Six new categories + nested toggle render + tooltip        |
| `web/src/lib/api.ts::ActivitySubSpan`                                          | TypeScript type for the new field                          |
| `tests/unit/test_activity_subphase_classifier.py`                              | 48 unit tests for classifier + merge                       |
| `tests/unit/test_activity_subphase_enrichment.py`                              | 15 integration tests for the enrichment pass               |
| `web/tests/e2e/activity-subphases.spec.ts`                                     | 5 Playwright tests for the UI                              |

## Operational notes

- The drilldown's `activity-detail-v2-<change>.jsonl` cache is bumped to
  `v3` so any agent run after this change rebuilds the cache to include
  the new `detail.file_path` field needed for accurate spec-vs-code
  distinction on absolute paths. Old `v2` cache files are silently
  ignored (no migration required, no breakage if both versions coexist).
- Custom test-runner scripts (`make e2e-flavor-x`) that don't match the
  documented Bash regex fall into `other` — they're still visible on the
  timeline, just unclassified. Patterns can be extended in
  `SUB_PHASE_TEST_RE` / `SUB_PHASE_BUILD_RE` without contract changes.
