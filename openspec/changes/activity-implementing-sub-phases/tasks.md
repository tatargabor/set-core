## 1. Classifier helper (`lib/set_orch/api/activity_detail.py`)

- [x] 1.1 Add a module-level constant `SUB_PHASE_TEST_RE` with the test command regex (`\b(pytest|jest|vitest|playwright|npm\s+(run\s+)?test|yarn\s+test|pnpm\s+(run\s+)?test|go\s+test|cargo\s+test)\b`, case-insensitive) and `SUB_PHASE_BUILD_RE` with the build regex (`\b(npm\s+run\s+build|next\s+build|tsc|cargo\s+build|make\s+(build|all)|bun\s+build)\b`, case-insensitive) [REQ: sub-phase-taxonomy]
- [x] 1.2 Add a module-level constant `SUB_PHASE_EXCLUDED_CATEGORIES` listing the drilldown categories to drop: `agent:llm-wait`, `agent:gap`, `agent:hook-overhead`, `agent:loop-restart`, `agent:review-wait`, `agent:verify-wait` [REQ: sub-phase-taxonomy]
- [x] 1.3 Implement `_classify_sub_span(span: dict) -> str | None` that takes a single drilldown sub-span and returns one of `spec`, `code`, `test`, `build`, `subagent`, `other`, or `None` if excluded; apply the priority order from the spec (excluded → subagent → edit/write/multiedit path → bash regex → other) [REQ: sub-phase-taxonomy]
- [x] 1.4 Implement `_merge_consecutive_sub_phases(items: list[dict], max_gap_ms: int = 30_000) -> list[dict]` that walks an already-classified, time-sorted list and collapses adjacent same-category entries when the inter-entry gap is ≤ `max_gap_ms`; first entry's `trigger_tool` / `trigger_detail` wins [REQ: consecutive-merge-rule]
- [x] 1.5 Implement `_classify_sub_phases(windowed_sub_spans: list[dict]) -> list[dict]` that takes the ALREADY-windowed list (caller passes the output of `_clip_and_filter`, no re-filtering), classifies each via `_classify_sub_span`, drops `None` results, sorts by `start`, calls `_merge_consecutive_sub_phases`, and returns entries with keys `category`, `start`, `end`, `duration_ms`, `trigger_tool`, `trigger_detail` (the latter two pulled from `detail.tool` and `detail.preview`) [REQ: sub-phase-taxonomy]

## 2. API enrichment hookup (`lib/set_orch/api/activity.py`)

- [x] 2.1 In the existing `implementing`-span enrichment block (around lines 1152-1206), import `_classify_sub_phases` alongside the existing `_build_sub_spans_for_change` / `_clip_and_filter` / `_compute_aggregates` imports [REQ: sub-spans-produced-by-the-existing-enrichment-pass]
- [x] 2.2 After the existing aggregate computation, call `_classify_sub_phases(window)` (passing the same `window = _clip_and_filter(sub_spans, span['start'], span['end'])` value already computed for the aggregates — no re-clip) and assign the result to `span['sub_spans']`; ensure `sub_spans` is set on every `implementing` span (use `[]` when no classifiable data) [REQ: implementing-spans-carry-a-sub-spans-field]
- [x] 2.3 Wrap the classifier call in a try/except that logs at DEBUG and falls back to `span['sub_spans'] = []` on any failure, mirroring the existing enrichment block's defensive style [REQ: sub-spans-produced-by-the-existing-enrichment-pass]
- [x] 2.4 Verify the per-change cache in the enrichment loop (`sub_span_cache`) is reused for both the existing aggregates and the new classification — no duplicate `_build_sub_spans_for_change` calls [REQ: sub-spans-produced-by-the-existing-enrichment-pass]
- [x] 2.5 Ensure every `implementing` span produced anywhere in `_build_spans` (step-transition close path, dispatch-fallback close path, end-of-stream flush) goes through the enrichment pass so they all get `sub_spans` (audit each emit site to confirm) [REQ: implementing-spans-carry-a-sub-spans-field]

## 3. Frontend nested rendering (`web/src/components/ActivityView.tsx`)

- [x] 3.1 Extend `CATEGORY_COLORS` with six entries: `implementing:spec`, `implementing:code`, `implementing:test`, `implementing:build`, `implementing:subagent`, `implementing:other` — distinct shades within the green family for spec/code/test/build, amber for subagent, gray for other [REQ: frontend-nested-rendering]
- [x] 3.2 Extend `CATEGORY_LABELS` with human-readable names for the six new sub-categories [REQ: frontend-nested-rendering]
- [x] 3.3 In the row renderer, detect `implementing` spans whose `sub_spans.length > 0`; render an expand/collapse toggle (▶/▼) on the row label [REQ: frontend-nested-rendering] — global toggle (single boolean), not per-change, for layout reasons (Gantt uses global category lanes); per-change drilldown still available via existing click-to-drill flow
- [x] 3.4 Persist expand state in `localStorage` under `activity-implementing-sub-expanded` (boolean `'true' | 'false'`); read on mount, write on toggle [REQ: frontend-nested-rendering] — single boolean instead of per-change Set, matching the global-toggle architecture
- [x] 3.5 When the toggle is expanded, six `implementing:*` lanes appear in CATEGORY_COLORS declaration order under the parent `implementing` lane, each rendering synthesized spans from every change's `sub_spans` with category-specific color; visual indentation via leading spaces in CATEGORY_LABELS [REQ: frontend-nested-rendering]
- [x] 3.6 Hover tooltip on sub-spans surfaces `category` (label), `duration`, `trigger_tool`, and `trigger_detail` truncated to 80 chars [REQ: implementing-spans-carry-a-sub-spans-field]
- [x] 3.7 Treat absent or empty `sub_spans` (or `null`, or non-array) as the no-toggle case — `hasSubPhases` check uses `Array.isArray(s.sub_spans) && s.sub_spans.length > 0` defensively [REQ: frontend-treats-missing-sub_spans-defensively]
- [x] 3.8 Parent-row tooltip computes per-category percentage from `sub_spans` and surfaces classified shares plus an `unclassified N% (wait/think)` footer indicating the share excluded from classification [REQ: parent-row-tooltip-exposes-per-category-percentage]

## 4. Tests: classifier unit (`tests/unit/test_activity_subphase_classifier.py`)

- [ ] 4.1 Edit/Write to `openspec/changes/foo/proposal.md` → `spec`; to `lib/foo.py` → `code`; to `openspec/specs/bar/spec.md` → `spec` [REQ: sub-phase-taxonomy]
- [ ] 4.2 Bash `pytest tests/unit` → `test`; `pnpm test:e2e` → `test`; `next build` → `build`; `tsc --noEmit` → `build`; `git status` → `other`; `cat foo.txt` → `other` [REQ: sub-phase-taxonomy]
- [ ] 4.3 `agent:subagent:explore-code` → `subagent`; `agent:subagent:review` → `subagent` [REQ: sub-phase-taxonomy]
- [ ] 4.4 `agent:tool:read` → `other`; `agent:tool:grep` → `other`; `agent:tool:webfetch` → `other`; unknown `agent:tool:foo` → `other` [REQ: sub-phase-taxonomy]
- [ ] 4.5 Excluded categories `agent:llm-wait`, `agent:gap`, `agent:hook-overhead`, `agent:loop-restart`, `agent:review-wait`, `agent:verify-wait` → `None` (excluded) [REQ: sub-phase-taxonomy]
- [ ] 4.6 Edit with missing or empty `detail.preview` → `code` (safe default) [REQ: sub-phase-taxonomy]
- [ ] 4.7 Two adjacent `code` sub-spans 5 sec apart → merge into one entry with first sub-span's trigger [REQ: consecutive-merge-rule]
- [ ] 4.8 Two adjacent `code` sub-spans 60 sec apart → remain separate [REQ: consecutive-merge-rule]
- [ ] 4.9 `code` followed immediately by `test` → two separate entries (different categories never merge) [REQ: consecutive-merge-rule]
- [ ] 4.10 200 consecutive `agent:tool:edit` sub-spans with sub-second gaps → single merged `code` entry spanning first.start to last.end [REQ: consecutive-merge-rule]
- [ ] 4.11 Window-clipping test: a sub-span partially outside the parent window is clipped to the window before classification [REQ: implementing-spans-carry-a-sub-spans-field]
- [ ] 4.12 No-classifiable-work test: window contains only `agent:llm-wait` → returns `[]` [REQ: sub-spans-do-not-need-to-cover-the-full-parent-duration]

## 5. Tests: API integration (`tests/unit/test_activity_api_subspans.py`)

- [ ] 5.1 Build a fixture project with one `implementing` span and a synthetic drilldown cache containing a mix of edit/bash/subagent sub-spans; hit `_build_spans` (or the API endpoint) and assert the resulting `implementing` span carries `sub_spans` with the expected categories and merged ranges [REQ: implementing-spans-carry-a-sub-spans-field]
- [ ] 5.2 Fixture with no drilldown sub-spans for the change → `sub_spans: []` (empty list, not missing or null) [REQ: implementing-spans-carry-a-sub-spans-field]
- [ ] 5.3 Fixture for the dispatch-fallback close path (no `STEP_TRANSITION`, only `DISPATCH` + terminal `STATE_CHANGE`) → sub-spans are still attached [REQ: implementing-spans-carry-a-sub-spans-field]
- [ ] 5.4 Fixture for the end-of-stream flush path (open `implementing` left dangling) → sub-spans are still attached [REQ: implementing-spans-carry-a-sub-spans-field]
- [ ] 5.5 Fixture asserting per-change cache reuse: monkey-patch `_build_sub_spans_for_change` with a counter; verify it's called at most once per change even when that change has multiple `implementing` spans [REQ: sub-spans-produced-by-the-existing-enrichment-pass]
- [ ] 5.6 Classifier-failure test: monkey-patch `_classify_sub_phases` to raise; assert the enrichment pass survives, that change's spans get `sub_spans: []`, other changes' spans are still classified [REQ: sub-spans-produced-by-the-existing-enrichment-pass]
- [ ] 5.7 Trigger-metadata round-trip: assert `detail.preview` and `detail.tool` from the drilldown surface as `trigger_detail` and `trigger_tool` on the rollup [REQ: sub-span-trigger-metadata-preservation]
- [ ] 5.8 Missing-metadata test: drilldown sub-span without `detail.tool` or `detail.preview` → rollup entry has `null` for the missing field(s) [REQ: sub-span-trigger-metadata-preservation]

## 6. Tests: frontend Playwright (`web/tests/e2e/`)

- [ ] 6.1 Add an E2E test that loads the Activity tab for a project whose `implementing` spans include `sub_spans`; assert the parent row shows the expand toggle [REQ: frontend-nested-rendering]
- [ ] 6.2 Click the toggle; assert sub-rows appear with the expected categories and colors; assert the localStorage entry updates [REQ: frontend-nested-rendering]
- [ ] 6.3 Reload the page; assert the previously expanded row re-renders expanded (localStorage persistence) [REQ: frontend-nested-rendering]
- [ ] 6.4 Load a project where `implementing` spans have empty `sub_spans`; assert no toggle appears and the row renders as today [REQ: frontend-nested-rendering]
- [ ] 6.5 Hover the parent row; assert the tooltip surfaces the per-category percentage breakdown including a "remainder unclassified" footer [REQ: parent-row-tooltip-exposes-per-category-percentage]
- [ ] 6.6 Defensive-render test: feed an API response where one `implementing` span has `sub_spans: null` and another has `sub_spans` missing entirely; assert both render as the no-toggle case without runtime errors [REQ: frontend-treats-missing-sub_spans-defensively]

## 7. Live consumer-project validation

- [ ] 7.1 After landing the change, open the Activity tab for a recently-completed orchestration run (any `*-run-*` project); verify each `implementing` row carries the new toggle and that expanding shows a meaningful spec/code/test/build/subagent/other split [REQ: implementing-spans-carry-a-sub-spans-field]
- [ ] 7.2 Cross-check the live breakdown against the same change's per-change drilldown view (`agent:tool:*` lane) for sanity — categories should be consistent rollups of the per-tool data [REQ: sub-phase-taxonomy]

## 8. Documentation

- [ ] 8.1 Add a section to the observability documentation describing the sub-phase taxonomy, the classification rules, the consecutive-merge property, and the "sub-spans don't sum to parent duration" property (with an explanation of why excluded categories exist) [REQ: sub-spans-do-not-need-to-cover-the-full-parent-duration]
- [ ] 8.2 Note that this change is server-side only — no consumer-project redeploy is required and the breakdown applies retroactively to historical runs [REQ: implementing-spans-carry-a-sub-spans-field]

## Acceptance Criteria (from spec scenarios)

### activity-sub-phases — sub-phase-taxonomy

- [ ] AC-1: WHEN a drilldown sub-span has `category = agent:tool:edit/write/multiedit` and `detail.preview` starts with `openspec/changes/` or `openspec/specs/` THEN the rollup category SHALL be `spec` [REQ: sub-phase-taxonomy, scenario: agent-tool-edit-to-openspec-artifact-path-classifies-as-spec]
- [ ] AC-2: WHEN a drilldown sub-span has `category = agent:tool:edit/write/multiedit` and `detail.preview` does not start with the OpenSpec prefixes THEN the rollup category SHALL be `code` [REQ: sub-phase-taxonomy, scenario: agent-tool-edit-to-non-openspec-path-classifies-as-code]
- [ ] AC-3: WHEN a drilldown sub-span has `category = agent:tool:bash` and `detail.preview` matches the test regex THEN the rollup category SHALL be `test` [REQ: sub-phase-taxonomy, scenario: agent-tool-bash-matching-test-pattern-classifies-as-test]
- [ ] AC-4: WHEN a drilldown sub-span has `category = agent:tool:bash` and `detail.preview` matches the build regex THEN the rollup category SHALL be `build` [REQ: sub-phase-taxonomy, scenario: agent-tool-bash-matching-build-pattern-classifies-as-build]
- [ ] AC-5: WHEN a drilldown sub-span has `category = agent:tool:bash` and `detail.preview` matches neither THEN the rollup category SHALL be `other` [REQ: sub-phase-taxonomy, scenario: agent-tool-bash-not-matching-test-or-build-classifies-as-other]
- [ ] AC-6: WHEN a drilldown sub-span has `category` starting with `agent:subagent:` THEN the rollup category SHALL be `subagent` [REQ: sub-phase-taxonomy, scenario: agent-subagent-classifies-as-subagent]
- [ ] AC-7: WHEN a drilldown sub-span has any other `agent:tool:<name>` category THEN the rollup category SHALL be `other` [REQ: sub-phase-taxonomy, scenario: other-tool-types-classify-as-other]
- [ ] AC-8: WHEN a drilldown sub-span has a wait or overhead `category` THEN it SHALL be excluded from the rollup [REQ: sub-phase-taxonomy, scenario: wait-and-overhead-categories-are-excluded]
- [ ] AC-9: WHEN a drilldown edit/write/multiedit sub-span has missing or empty `detail.preview` THEN the rollup category SHALL be `code` [REQ: sub-phase-taxonomy, scenario: classification-missing-detailpreview]

### activity-sub-phases — consecutive-merge-rule

- [ ] AC-10: WHEN two consecutive `code` sub-spans have a gap ≤ 30 sec THEN they SHALL merge into one entry with the first's trigger [REQ: consecutive-merge-rule, scenario: adjacent-same-category-sub-spans-within-30-sec-merge]
- [ ] AC-11: WHEN two consecutive `code` sub-spans have a gap > 30 sec THEN they SHALL remain separate [REQ: consecutive-merge-rule, scenario: adjacent-same-category-sub-spans-more-than-30-sec-apart-do-not-merge]
- [ ] AC-12: WHEN a `code` sub-span is immediately followed by a `test` sub-span THEN they SHALL appear as two separate entries [REQ: consecutive-merge-rule, scenario: different-categories-do-not-merge-across-boundaries]
- [ ] AC-13: WHEN 200 consecutive `agent:tool:edit` sub-spans with sub-second gaps appear THEN the rollup SHALL contain a single `code` entry spanning first.start to last.end [REQ: consecutive-merge-rule, scenario: long-run-of-micro-spans-collapses-to-one-range]

### activity-sub-phases — sub-spans-do-not-need-to-cover-the-full-parent-duration

- [ ] AC-14: WHEN a 600-sec parent has 400 sec of `agent:llm-wait` and 200 sec of `agent:tool:edit` THEN `sub_spans` SHALL contain only the `code` entries totaling 200 sec; the API consumer SHALL NOT assume coverage equals duration [REQ: sub-spans-do-not-need-to-cover-the-full-parent-duration, scenario: long-parent-with-mostly-llm-wait]
- [ ] AC-15: WHEN a parent's drilldown sub-spans are entirely excluded categories THEN `sub_spans` SHALL be `[]` [REQ: sub-spans-do-not-need-to-cover-the-full-parent-duration, scenario: parent-with-no-classifiable-work]

### activity-sub-phases — frontend-nested-rendering

- [ ] AC-16: WHEN the Activity tab opens for the first time and the row has sub-spans THEN the row SHALL render with a collapsed toggle and the parent SHALL render in its existing color [REQ: frontend-nested-rendering, scenario: implementing-row-with-sub-spans-collapsed-by-default]
- [ ] AC-17: WHEN the user clicks the expand toggle THEN indented sub-rows SHALL appear with category colors and the expand state SHALL be persisted in `localStorage` [REQ: frontend-nested-rendering, scenario: expanding-a-row-reveals-indented-sub-rows]
- [ ] AC-18: WHEN an `implementing` span has empty `sub_spans` THEN no toggle SHALL appear and the row SHALL render as a single block [REQ: frontend-nested-rendering, scenario: implementing-row-without-sub-spans-renders-as-today]
- [ ] AC-19: WHEN sub-rows render THEN colors SHALL be drawn from the fixed palette and a tooltip SHALL surface the category on hover [REQ: frontend-nested-rendering, scenario: sub-row-color-shades]
- [ ] AC-20: WHEN the API response omits `sub_spans`, returns `null`, or returns a non-array THEN the frontend SHALL treat it as `[]` and render the parent row as today without runtime error [REQ: frontend-nested-rendering, scenario: frontend-treats-missing-sub_spans-defensively]
- [ ] AC-21: WHEN the user hovers the parent `implementing` row THEN the tooltip SHALL include a per-category percentage breakdown and a remainder indicator [REQ: frontend-nested-rendering, scenario: parent-row-tooltip-exposes-per-category-percentage]

### activity-timeline-api — implementing-spans-carry-a-sub-spans-field

- [ ] AC-22: WHEN the API returns an `implementing` span whose drilldown window contains only excluded categories or no sub-spans THEN the span SHALL include `sub_spans: []` [REQ: implementing-spans-carry-a-sub-spans-field, scenario: implementing-span-with-no-classifiable-drilldown-sub-spans]
- [ ] AC-23: WHEN the API returns an `implementing` span with classifiable drilldown sub-spans THEN every entry SHALL have `category`, `start`, `end`, `duration_ms`, `trigger_tool`, `trigger_detail`; entries SHALL be `start`-ascending and non-overlapping [REQ: implementing-spans-carry-a-sub-spans-field, scenario: implementing-span-with-classifiable-drilldown-sub-spans]
- [ ] AC-24: WHEN the API returns an `implementing` span with `sub_spans` THEN every entry SHALL be confined to the parent's `[start, end]` window [REQ: implementing-spans-carry-a-sub-spans-field, scenario: sub-spans-are-confined-to-the-parents-time-window]
- [ ] AC-25: WHEN the API returns an `implementing` span with `sub_spans` THEN the union of durations MAY be less than the parent's `duration_ms` [REQ: implementing-spans-carry-a-sub-spans-field, scenario: sub-spans-need-not-cover-the-parents-full-duration]

### activity-timeline-api — sub-spans-produced-by-the-existing-enrichment-pass

- [ ] AC-26: WHEN the API response covers multiple `implementing` spans for the same change THEN `_build_sub_spans_for_change` SHALL be called at most once per change and the data SHALL be reused for both aggregates and classification [REQ: sub-spans-produced-by-the-existing-enrichment-pass, scenario: drilldown-cache-is-loaded-at-most-once-per-change]
- [ ] AC-27: WHEN the classifier raises while processing one change's data THEN the failure SHALL be logged at DEBUG, that change's spans SHALL still receive `sub_spans: []`, and other changes SHALL still be classified normally [REQ: sub-spans-produced-by-the-existing-enrichment-pass, scenario: classifier-failure-does-not-break-the-enrichment-pass]

### activity-timeline-api — sub-span-trigger-metadata-preservation

- [ ] AC-28: WHEN a drilldown sub-span has `detail.tool = "Edit"` and `detail.preview = "openspec/changes/foo/proposal.md"` THEN the rollup SHALL carry `trigger_tool = "Edit"` and `trigger_detail = "openspec/changes/foo/proposal.md"` [REQ: sub-span-trigger-metadata-preservation, scenario: trigger-metadata-flows-from-drilldown-detailpreview]
- [ ] AC-29: WHEN five drilldown sub-spans contribute to one merged rollup entry THEN the merged entry's trigger SHALL be that of the first contributing sub-span [REQ: sub-span-trigger-metadata-preservation, scenario: merged-range-carries-the-first-sub-spans-trigger-only]
- [ ] AC-30: WHEN the contributing drilldown sub-span has no `detail.tool` or no `detail.preview` THEN the rollup entry SHALL still be produced with `null` for the missing field(s) [REQ: sub-span-trigger-metadata-preservation, scenario: missing-trigger-metadata-in-source]
