## ADDED Requirements

<!--
IN SCOPE:
- Server-side classification of the existing per-change drilldown sub-spans into a six-bucket operator-facing taxonomy.
- A fixed v1 sub-phase taxonomy: `spec`, `code`, `test`, `build`, `subagent`, `other`.
- Mapping rules from the drilldown's `agent:tool:<name>` and `agent:subagent:*` categories (plus their `detail.preview`) into the operator-facing taxonomy.
- A consecutive-merge rule that collapses adjacent same-category sub-spans within a 30-second tolerance into single ranges.
- Frontend rendering as nested expandable rows under the parent `implementing` lane, with persistent per-change expand state.
- Reuse of the existing drilldown cache and the existing `implementing`-span enrichment pass — no new files, no new event types, no agent-side touchpoints.
- Backward compatibility for runs predating this change (works retroactively because the source data already exists).

OUT OF SCOPE:
- Sub-phase decomposition for `planning` or `fixing` lifecycle phases.
- Sub-agent internal timeline (already covered by the existing per-change drilldown's `agent:subagent:*` lane).
- LLM-wait, gap, hook-overhead, loop-restart, review-wait, verify-wait sub-spans (deliberately excluded — sub_spans represents classifiable work only, not full time coverage).
- Read, Grep, Glob as separate sub-phases (they fall into `other`).
- Bash command pattern coverage beyond the documented test/build regexes (everything else falls into `other`).
- Live event emission, agent-side hooks, settings.json or `set-deploy-hooks` modifications, consumer-project redeploy.
- A user-configurable taxonomy or custom classification rules.
-->

### Requirement: Sub-phase taxonomy

The system SHALL classify every drilldown sub-span produced by `activity_detail.py` for the window of an `implementing` parent into exactly one of six operator-facing categories: `spec`, `code`, `test`, `build`, `subagent`, `other`. Categories that represent waits or non-classifiable work SHALL be excluded from the rollup entirely.

#### Scenario: `agent:tool:edit` to OpenSpec artifact path classifies as `spec`

- **WHEN** a drilldown sub-span has `category = "agent:tool:edit"` (or `"agent:tool:write"` or `"agent:tool:multiedit"`) and `detail.preview` starts with `openspec/changes/` or `openspec/specs/`
- **THEN** the rollup category SHALL be `spec`

#### Scenario: `agent:tool:edit` to non-OpenSpec path classifies as `code`

- **WHEN** a drilldown sub-span has `category = "agent:tool:edit"` (or `"agent:tool:write"` or `"agent:tool:multiedit"`) and `detail.preview` does NOT start with `openspec/changes/` or `openspec/specs/`
- **THEN** the rollup category SHALL be `code`

#### Scenario: `agent:tool:bash` matching test pattern classifies as `test`

- **WHEN** a drilldown sub-span has `category = "agent:tool:bash"` and `detail.preview` matches the test regex `\b(pytest|jest|vitest|playwright|npm\s+(run\s+)?test|yarn\s+test|pnpm\s+(run\s+)?test|go\s+test|cargo\s+test)\b` (case-insensitive)
- **THEN** the rollup category SHALL be `test`

#### Scenario: `agent:tool:bash` matching build pattern classifies as `build`

- **WHEN** a drilldown sub-span has `category = "agent:tool:bash"` and `detail.preview` matches the build regex `\b(npm\s+run\s+build|next\s+build|tsc|cargo\s+build|make\s+(build|all)|bun\s+build)\b` (case-insensitive)
- **THEN** the rollup category SHALL be `build`

#### Scenario: `agent:tool:bash` not matching test or build classifies as `other`

- **WHEN** a drilldown sub-span has `category = "agent:tool:bash"` and `detail.preview` matches neither the test nor the build regex
- **THEN** the rollup category SHALL be `other`

#### Scenario: `agent:subagent:*` classifies as `subagent`

- **WHEN** a drilldown sub-span has a `category` starting with `agent:subagent:`
- **THEN** the rollup category SHALL be `subagent`

#### Scenario: Other tool types classify as `other`

- **WHEN** a drilldown sub-span has `category` equal to `agent:tool:read`, `agent:tool:grep`, `agent:tool:glob`, `agent:tool:webfetch`, `agent:tool:websearch`, `agent:tool:notebookedit`, `agent:tool:todowrite`, `agent:tool:other`, or any other `agent:tool:<name>` not covered above
- **THEN** the rollup category SHALL be `other`

#### Scenario: Wait and overhead categories are excluded

- **WHEN** a drilldown sub-span has `category` equal to `agent:llm-wait`, `agent:gap`, `agent:hook-overhead`, `agent:loop-restart`, `agent:review-wait`, or `agent:verify-wait`
- **THEN** the sub-span SHALL be excluded from the rollup
- **AND** SHALL NOT contribute to any sub_spans entry

#### Scenario: Classification missing `detail.preview`

- **WHEN** a drilldown sub-span has `category = "agent:tool:edit"` (or write / multiedit) but `detail.preview` is missing or empty
- **THEN** the rollup category SHALL be `code` (the safe default — assumes non-OpenSpec work)

### Requirement: Consecutive-merge rule

The classifier SHALL merge adjacent rollup sub-spans of the same category into single ranges when the gap between them is at most 30 seconds. The merged range's `start` SHALL be the first sub-span's `start`, its `end` SHALL be the last sub-span's `end`, and `trigger_tool` / `trigger_detail` SHALL be carried from the first sub-span only.

#### Scenario: Adjacent same-category sub-spans within 30 sec merge

- **GIVEN** two consecutive rollup sub-spans of category `code` where the second starts within 30 seconds of the first's end
- **WHEN** the classifier produces the final list
- **THEN** the two SHALL be replaced by a single entry whose `start` is the first's `start`, `end` is the second's `end`, and `trigger_tool` / `trigger_detail` are taken from the first

#### Scenario: Adjacent same-category sub-spans more than 30 sec apart do not merge

- **GIVEN** two consecutive rollup sub-spans of category `code` where the gap between them is greater than 30 seconds
- **WHEN** the classifier produces the final list
- **THEN** the two SHALL appear as separate entries

#### Scenario: Different categories do not merge across boundaries

- **GIVEN** a rollup sub-span of category `code` followed by one of category `test` with no gap
- **WHEN** the classifier produces the final list
- **THEN** they SHALL appear as two separate entries (different categories never merge)

#### Scenario: Long run of micro-spans collapses to one range

- **GIVEN** 200 consecutive `agent:tool:edit` sub-spans (all classifying to `code`) with sub-second gaps between them
- **WHEN** the classifier produces the final list
- **THEN** the result SHALL contain a single `code` entry whose `start` is the first sub-span's `start` and whose `end` is the last sub-span's `end`

### Requirement: Sub-spans do not need to cover the full parent duration

The system SHALL NOT require the union of `sub_spans` entries to cover the parent `implementing` span's `[start, end]` window. Excluded categories (waits, gaps, overhead) and unclassifiable time SHALL leave gaps in the coverage.

#### Scenario: Long parent with mostly LLM-wait

- **GIVEN** an `implementing` parent of 600 seconds where the agent spent 400 seconds in `agent:llm-wait` (think time) and 200 seconds in `agent:tool:edit` calls
- **WHEN** the classifier produces the final list
- **THEN** the `sub_spans` SHALL contain only the `code` entries totaling 200 seconds
- **AND** the API consumer SHALL NOT assume the entries sum to the parent's 600-second duration

#### Scenario: Parent with no classifiable work

- **GIVEN** an `implementing` parent whose drilldown sub-spans are entirely `agent:llm-wait` and `agent:gap`
- **WHEN** the classifier produces the final list
- **THEN** `sub_spans` SHALL be `[]` (empty list, not `null`)

### Requirement: Frontend nested rendering

The Activity dashboard SHALL render `implementing` rows with an expand/collapse toggle when the parent span carries one or more sub-spans, and SHALL render indented sub-rows in distinct color shades when the row is expanded.

#### Scenario: Implementing row with sub-spans collapsed by default

- **GIVEN** an `implementing` span carries a non-empty `sub_spans` list
- **WHEN** the Activity tab is opened for the first time (no persisted expand state for this change)
- **THEN** the row SHALL render with a collapse/expand toggle on the row label
- **AND** the row SHALL be in the collapsed state
- **AND** the parent span SHALL render in its existing color and full duration

#### Scenario: Expanding a row reveals indented sub-rows

- **WHEN** the user clicks the expand toggle on an `implementing` row that has sub-spans
- **THEN** the row SHALL transition to expanded state
- **AND** indented sub-rows SHALL appear below the parent, one per distinct sub-span category present in the data
- **AND** each sub-row SHALL render its sub-spans with a category-specific color shade
- **AND** the expand state SHALL be persisted in `localStorage` keyed by change name

#### Scenario: Implementing row without sub-spans renders as today

- **GIVEN** an `implementing` span has an empty `sub_spans` list
- **WHEN** the Activity tab renders the row
- **THEN** no expand/collapse toggle SHALL be shown on the row label
- **AND** the row SHALL render as a single block in the existing color

#### Scenario: Sub-row color shades

- **WHEN** sub-rows render
- **THEN** the colors SHALL be drawn from a fixed palette — distinct shades within the green family for `spec`, `code`, `test`, and `build`; amber for `subagent`; gray for `other`
- **AND** a tooltip SHALL surface the category name on hover

#### Scenario: Frontend treats missing `sub_spans` defensively

- **WHEN** the API response omits the `sub_spans` field, returns `null`, or returns a non-array value
- **THEN** the frontend SHALL treat the value as an empty list and render the parent row as today
- **AND** SHALL NOT raise a runtime error

#### Scenario: Parent row tooltip exposes per-category percentage

- **WHEN** the user hovers the parent `implementing` row
- **THEN** the tooltip SHALL include a per-category time breakdown (e.g., `spec 18% · code 47% · test 12% · build 4% · subagent 5% · other 14%`)
- **AND** SHALL surface the share of the parent's duration covered by classifiable work (the remainder is unclassified wait/think time)
